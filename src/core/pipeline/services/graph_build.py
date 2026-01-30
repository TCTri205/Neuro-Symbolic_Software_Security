import ast
import os
from typing import Any, Callable, Dict, Optional, Tuple

from src.core.cfg.builder import CFGBuilder
from src.core.cfg.callgraph import CallGraph, CallGraphBuilder
from src.core.cfg.synthetic import SyntheticEdgeBuilder
from src.core.pipeline.interfaces import (
    CFGBuilderPort,
    CallGraphBuilderPort,
    GraphBuildPort,
    SyntheticEdgeBuilderPort,
)
from src.core.telemetry import MeasureLatency


class GraphBuildService(GraphBuildPort):
    def __init__(
        self,
        logger,
        cfg_builder: Optional[CFGBuilderPort] = None,
        call_graph_builder_factory: Optional[
            Callable[[CallGraph], CallGraphBuilderPort]
        ] = None,
        synthetic_builder_factory: Optional[
            Callable[[CallGraph], SyntheticEdgeBuilderPort]
        ] = None,
    ) -> None:
        self.logger = logger
        self.cfg_builder = cfg_builder or CFGBuilder()
        self.call_graph_builder_factory = call_graph_builder_factory or CallGraphBuilder
        self.synthetic_builder_factory = (
            synthetic_builder_factory or SyntheticEdgeBuilder
        )

    def build_cfg_and_call_graph(
        self,
        source_code: str,
        file_path: str,
        semgrep_results: Dict[str, Any],
    ) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
        try:
            with MeasureLatency("build_cfg_cg"):
                tree = ast.parse(source_code, filename=file_path)

                call_graph = CallGraph()
                cg_builder = self.call_graph_builder_factory(call_graph)
                cg_builder.extract_definitions(tree)

                module_name = (
                    os.path.basename(file_path).replace(".py", "")
                    if file_path != "<unknown>"
                    else "module"
                )
                cfg = self.cfg_builder.build(module_name, tree)

                if semgrep_results:
                    self._map_semgrep_findings(cfg, semgrep_results, file_path)

                cg_builder.build_from_cfg(cfg)

                synth_builder = self.synthetic_builder_factory(call_graph)
                synth_builder.process(tree, cfg)

                return cfg, call_graph, None
        except Exception as e:
            msg = f"CFG/CallGraph construction failed: {e}"
            self.logger.error(msg)
            return None, None, msg

    def _map_semgrep_findings(
        self, cfg, semgrep_results: Dict[str, Any], file_path: str
    ) -> None:
        findings = semgrep_results.get("results", [])
        if not findings:
            return

        target_path = os.path.abspath(file_path)
        unmapped = semgrep_results.setdefault("unmapped", [])

        for finding in findings:
            finding_path = finding.get("path")
            if finding_path:
                if os.path.abspath(finding_path) != target_path:
                    if not target_path.endswith(finding_path):
                        continue

            start = finding.get("start", {})
            line = start.get("line")
            if not line:
                unmapped.append(finding)
                continue

            block = self._find_block_by_line(cfg, line)
            if not block:
                unmapped.append(finding)
                continue

            finding_info = {
                "check_id": finding.get("check_id"),
                "message": finding.get("extra", {}).get("message"),
                "severity": finding.get("extra", {}).get("severity"),
                "line": line,
                "column": start.get("col"),
            }
            block.security_findings.append(finding_info)

    def _find_block_by_line(self, cfg, line: int) -> Optional[Any]:
        for block in cfg._blocks.values():
            for stmt in block.statements:
                start = getattr(stmt, "lineno", None)
                if start is None:
                    continue
                end = getattr(stmt, "end_lineno", start)
                if start <= line <= end:
                    return block
        return None

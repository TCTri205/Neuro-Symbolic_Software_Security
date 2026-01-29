from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import ast
import os
import json

from src.core.cfg.builder import CFGBuilder
from src.core.cfg.callgraph import CallGraph, CallGraphBuilder
from src.core.cfg.synthetic import SyntheticEdgeBuilder
from src.core.cfg.ssa.transformer import SSATransformer
from src.core.parser import PythonAstParser
from src.core.parser.obfuscation import detect_obfuscation, is_binary_extension
from src.core.scan.secrets import SecretScanner, SecretMatch
from src.core.scan.baseline import BaselineEngine
from src.core.privacy.masker import PrivacyMasker
from src.core.analysis.sanitizers import SanitizerRegistry
from src.core.telemetry import get_logger, MeasureLatency
from src.core.risk.ranker import RankerService
from src.core.risk.routing import RoutingService
from src.core.risk.schema import RankerOutput, RoutingPlan
from src.core.taint.engine import (
    TaintConfiguration,
    TaintEngine,
    TaintFlow,
    TaintSink,
    TaintSource,
)

from src.core.ai.prompts import SecurityPromptBuilder
from src.core.scan.semgrep import SemgrepRunner
from src.core.ai.client import LLMClient
from src.core.pipeline.gatekeeper import GatekeeperService
from src.librarian import Librarian

DEFAULT_TAINT_SOURCES = [
    "input",
    "os.getenv",
    "getenv",
    "request.args.get",
    "request.form.get",
    "request.get_json",
]

DEFAULT_TAINT_SINKS = [
    "exec",
    "eval",
    "os.system",
    "subprocess.run",
    "subprocess.call",
    "open",
    "print",
]


@dataclass
class AnalysisResult:
    file_path: str
    cfg: Optional[Any] = None
    ssa: Optional[Any] = None
    call_graph: Optional[Any] = None
    ir: Optional[Any] = None
    semgrep_results: Dict[str, Any] = field(default_factory=dict)
    secrets: List[SecretMatch] = field(default_factory=list)
    masked_code: Optional[str] = None
    mask_mapping: Optional[Dict[str, str]] = None
    taint_flows: List[TaintFlow] = field(default_factory=list)
    ranker_output: Optional[RankerOutput] = None
    routing: Optional[RoutingPlan] = None
    errors: List[str] = field(default_factory=list)
    baseline_stats: Optional[Dict[str, int]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize results to dictionary format compatible with reports."""
        if not self.cfg:
            return {"error": "; ".join(self.errors)} if self.errors else {}

        blocks = []
        for block in self.cfg._blocks.values():
            phis = [str(p) for p in block.phi_nodes]
            blocks.append(
                {
                    "id": block.id,
                    "scope": block.scope,
                    "stmt_count": len(block.statements),
                    "phis": phis,
                    "security_findings": block.security_findings,
                    "llm_insights": block.llm_insights,
                }
            )

        edges = []
        for u, v, data in self.cfg.graph.edges(data=True):
            edges.append({"source": u, "target": v, "label": data.get("label")})

        cg_nodes = []
        cg_edges = []
        if self.call_graph:
            for n, data in self.call_graph.graph.nodes(data=True):
                cg_nodes.append({"id": n, "kind": data.get("kind")})
            for u, v, data in self.call_graph.graph.edges(data=True):
                cg_edges.append({"source": u, "target": v, "type": data.get("type")})

        # SSA stats
        var_count = len(self.ssa.vars) if self.ssa else 0

        payload = {
            "name": self.cfg.name,
            "stats": {
                "block_count": len(self.cfg._blocks),
                "edge_count": len(self.cfg.graph.edges),
                "var_count": var_count,
                "cg_node_count": len(cg_nodes),
                "cg_edge_count": len(cg_edges),
            },
            "structure": {"blocks": blocks, "edges": edges},
            "call_graph": {"nodes": cg_nodes, "edges": cg_edges},
            "semgrep": self.semgrep_results,
            "secrets": [s.__dict__ for s in self.secrets],
            "errors": self.errors,
        }
        if self.ir:
            payload["ir"] = self.ir
        if self.taint_flows:
            payload["taint_flows"] = [flow.model_dump() for flow in self.taint_flows]
        if self.ranker_output:
            payload["risk"] = self.ranker_output.model_dump()
        if self.routing:
            payload["routing"] = self.routing.model_dump()
        if self.baseline_stats:
            payload["baseline"] = self.baseline_stats
        return payload


class AnalysisOrchestrator:
    """
    Orchestrates the security analysis pipeline:
    1. Static Scanning (Secrets)
    2. Semgrep Analysis
    3. CFG Construction & Call Graph
    4. SSA Transformation
    5. Privacy Masking (Optional)
    6. LLM Analysis (with Librarian caching)
    """

    def __init__(
        self,
        enable_ir: bool = False,
        enable_docstring_stripping: bool = False,
        taint_config: Optional[TaintConfiguration] = None,
        baseline_mode: bool = False,
    ):
        self.secret_scanner = SecretScanner()
        self.privacy_masker = PrivacyMasker()
        self.sanitizer_registry = SanitizerRegistry()
        self.librarian = Librarian()
        self.prompt_builder = SecurityPromptBuilder()
        self.logger = get_logger(__name__)
        self.enable_ir = enable_ir
        self.enable_docstring_stripping = enable_docstring_stripping
        self.baseline_engine = BaselineEngine() if baseline_mode else None
        self.taint_engine = TaintEngine()
        self.ranker = RankerService()
        self.router = RoutingService()
        self.gatekeeper = GatekeeperService()
        self.taint_config = taint_config or TaintConfiguration(
            sources=[TaintSource(name=source) for source in DEFAULT_TAINT_SOURCES],
            sinks=[TaintSink(name=sink) for sink in DEFAULT_TAINT_SINKS],
            sanitizers=list(SanitizerRegistry._DEFAULT_MAPPING.keys()),
        )

        # Determine semgrep config
        rules_path = os.path.join(os.getcwd(), "rules", "nsss-python-owasp.yml")
        semgrep_config = "auto"
        if os.path.exists(rules_path):
            semgrep_config = rules_path
        self.semgrep_runner = SemgrepRunner(config=semgrep_config)

    def analyze_code(
        self, source_code: str, file_path: str = "<unknown>"
    ) -> AnalysisResult:
        result = AnalysisResult(file_path=file_path)
        self.gatekeeper.reset_scan()
        source_lines = source_code.splitlines()

        # Step 1: Secret Scanning (on original code)
        try:
            with MeasureLatency("scan_secrets"):
                result.secrets = self.secret_scanner.scan(source_code)
        except Exception as e:
            msg = f"Secret scanning failed: {e}"
            self.logger.error(msg)
            result.errors.append(msg)

        is_obfuscated, reasons = detect_obfuscation(source_code)
        if is_obfuscated:
            reason_text = ", ".join(reasons) if reasons else "heuristics"
            msg = (
                f"Obfuscated code detected ({reason_text}). "
                "Skipping structural analysis."
            )
            self.logger.warning(msg)
            result.errors.append(msg)
            return result

        # Step 2: Semgrep (requires file path usually)
        if file_path and file_path != "<unknown>":
            try:
                with MeasureLatency("semgrep_scan"):
                    result.semgrep_results = self.semgrep_runner.run(file_path)
            except Exception as e:
                msg = f"Semgrep scan failed: {e}"
                self.logger.error(msg)
                result.errors.append(msg)

        # Step 2.5: IR (optional)
        if self.enable_ir:
            try:
                with MeasureLatency("parse_ir"):
                    parser = PythonAstParser(
                        source_code,
                        file_path,
                        enable_docstring_stripping=self.enable_docstring_stripping,
                    )
                    result.ir = parser.parse().model_dump(by_alias=True)
            except Exception as e:
                msg = f"IR parsing failed: {e}"
                self.logger.error(msg)
                result.errors.append(msg)

        # Step 3: CFG & Call Graph Construction
        try:
            with MeasureLatency("build_cfg_cg"):
                tree = ast.parse(source_code, filename=file_path)

                # Call Graph Init
                call_graph = CallGraph()
                cg_builder = CallGraphBuilder(call_graph)

                # Phase 1: Extract definitions
                cg_builder.extract_definitions(tree)

                # CFG Build
                builder = CFGBuilder()
                module_name = (
                    os.path.basename(file_path).replace(".py", "")
                    if file_path != "<unknown>"
                    else "module"
                )
                cfg = builder.build(module_name, tree)

                # Map Semgrep findings to CFG
                if result.semgrep_results:
                    self._map_semgrep_findings(cfg, result.semgrep_results, file_path)

                if self.baseline_engine:
                    stats, filtered_secrets = self._apply_baseline_filter(
                        cfg, file_path, source_lines, result.secrets
                    )
                    result.baseline_stats = stats
                    result.secrets = filtered_secrets

                # Phase 2: Build Call Graph from CFG
                cg_builder.build_from_cfg(cfg)

                # Phase 3: Add Synthetic Edges (Implicit Flows)
                synth_builder = SyntheticEdgeBuilder(call_graph)
                synth_builder.process(tree, cfg)

                result.cfg = cfg
                result.call_graph = call_graph

        except Exception as e:
            msg = f"CFG/CallGraph construction failed: {e}"
            self.logger.error(msg)
            result.errors.append(msg)
            # If CFG fails, we can't do SSA or LLM properly on structure
            return result

        # Step 4: SSA Transformation
        try:
            with MeasureLatency("ssa_transform"):
                ssa = SSATransformer(result.cfg)
                ssa.analyze()
                result.ssa = ssa
        except Exception as e:
            msg = f"SSA transformation failed: {e}"
            self.logger.error(msg)
            result.errors.append(msg)

        # Step 4.5: Taint Analysis + Ranking + Routing
        try:
            with MeasureLatency("taint_ranking"):
                if result.ssa and result.cfg:
                    result.taint_flows = self.taint_engine.analyze(
                        result.cfg, result.ssa.ssa_map, self.taint_config
                    )
                    result.ranker_output = self.ranker.rank(result.taint_flows)
                    result.routing = self.router.route(result.ranker_output)
        except Exception as e:
            msg = f"Taint ranking failed: {e}"
            self.logger.error(msg)
            result.errors.append(msg)

        # Step 5: LLM Analysis
        try:
            with MeasureLatency("llm_analysis"):
                if result.ssa and result.cfg:
                    self._run_llm_analysis(
                        result.cfg, result.ssa, source_code, file_path
                    )
        except Exception as e:
            msg = f"LLM analysis failed: {e}"
            self.logger.error(msg)
            result.errors.append(msg)

        # Step 6: Privacy Masking (Optional, for demo/verification)
        try:
            with MeasureLatency("privacy_masking"):
                masked_code, mapping = self.privacy_masker.mask(source_code)
                result.masked_code = masked_code
                result.mask_mapping = mapping
        except Exception as e:
            msg = f"Privacy masking failed: {e}"
            self.logger.error(msg)
            result.errors.append(msg)

        return result

    def baseline_summary(self) -> Optional[Dict[str, int]]:
        if not self.baseline_engine:
            return None
        return self.baseline_engine.summary()

    def analyze_file(self, file_path: str) -> AnalysisResult:
        if is_binary_extension(file_path):
            msg = f"Skipping binary file: {file_path}"
            self.logger.warning(msg)
            return AnalysisResult(file_path=file_path, errors=[msg])
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()
            return self.analyze_code(source_code, file_path)
        except Exception as e:
            self.logger.error(f"Failed to read file {file_path}: {e}")
            return AnalysisResult(file_path=file_path, errors=[f"File read error: {e}"])

    # --- Helper methods from Legacy Pipeline ---

    def _map_semgrep_findings(
        self, cfg, semgrep_results: Dict[str, Any], file_path: str
    ):
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

    def _run_llm_analysis(self, cfg, ssa, source: str, file_path: str):
        provider = self.gatekeeper.preferred_provider()
        client = LLMClient(provider=provider)
        if not client.is_configured:
            return

        source_lines = source.splitlines()
        for block in cfg._blocks.values():
            if not block.security_findings:
                continue

            snippet = self._extract_block_source(block, source_lines)
            if not snippet:
                continue

            ssa_context = self._build_ssa_context(block, ssa)
            prompt = self.prompt_builder.build_analysis_prompt(
                block, snippet, file_path, ssa_context
            )

            # Determine primary check_id for semantic lookup
            primary_check_id = ""
            if block.security_findings:
                primary_check_id = block.security_findings[0].get("check_id", "")

            # Check Librarian for cached decision
            cached_insight = self.librarian.query(
                prompt, check_id=primary_check_id, snippet=snippet
            )
            if cached_insight:
                cached_insight["snippet"] = snippet
                block.llm_insights.append(cached_insight)
                continue

            decision = self.gatekeeper.evaluate(prompt=prompt, client=client)
            if not decision.allowed:
                self.logger.info(
                    f"Skipping LLM analysis for {file_path}: {decision.reason}"
                )
                continue

            response = client.chat(prompt)
            self.gatekeeper.record_response(client, response, decision)
            insight = {
                "provider": client.provider,
                "model": client.model,
                "response": response.get("content"),
                "error": response.get("error"),
                "snippet": snippet,
            }

            # Attempt to parse JSON from content
            content = response.get("content")
            if content:
                try:
                    # Strip markdown code blocks
                    clean_content = content.strip()
                    if clean_content.startswith("```json"):
                        clean_content = clean_content[7:]
                    elif clean_content.startswith("```"):
                        clean_content = clean_content[3:]

                    if clean_content.endswith("```"):
                        clean_content = clean_content[:-3]

                    clean_content = clean_content.strip()

                    parsed = json.loads(clean_content)
                    if isinstance(parsed, dict) and "analysis" in parsed:
                        analysis = parsed["analysis"]
                        if isinstance(analysis, list):
                            for item in analysis:
                                if not isinstance(item, dict):
                                    continue
                                if "fix_suggestion" not in item and item.get(
                                    "remediation"
                                ):
                                    item["fix_suggestion"] = item.get("remediation")
                                if "remediation" not in item and item.get(
                                    "fix_suggestion"
                                ):
                                    item["remediation"] = item.get("fix_suggestion")
                                if "secure_code_snippet" not in item:
                                    secure_code = item.get("secure_code")
                                    if secure_code:
                                        item["secure_code_snippet"] = secure_code
                            insight["analysis"] = analysis
                except Exception:
                    # Failed to parse, valid JSON might not be returned
                    pass

            # Store in Librarian if successful
            if not insight.get("error") and content:
                self.librarian.store(
                    prompt,
                    content,
                    insight.get("analysis", []),
                    client.model,
                    snippet=snippet,
                    check_id=primary_check_id,
                )

            if "status" in response:
                insight["status"] = response["status"]
            if "body" in response:
                insight["body"] = response["body"]
            if "raw" in response:
                insight["raw"] = response["raw"]
            block.llm_insights.append(insight)

    def _apply_baseline_filter(
        self,
        cfg,
        file_path: str,
        source_lines: List[str],
        secrets: Optional[List[SecretMatch]] = None,
    ) -> Any:  # Returns Tuple[Dict[str, int], List[SecretMatch]]
        new_count = 0
        existing_count = 0

        for block in cfg._blocks.values():
            if not block.security_findings:
                continue
            filtered, stats = self.baseline_engine.filter_findings(
                block.security_findings, file_path, source_lines
            )
            block.security_findings = filtered
            new_count += stats.get("new", 0)
            existing_count += stats.get("existing", 0)

        filtered_secrets = []
        if secrets:
            secret_findings = []
            for s in secrets:
                # Create a finding dict that BaselineEngine can understand
                secret_findings.append(
                    {
                        "check_id": f"secret.{s.type.replace(' ', '_').lower()}",
                        "message": f"Found {s.type}",
                        "line": s.line,
                        "column": 1,
                        "severity": "CRITICAL",
                        "_original_secret": s,
                    }
                )

            filtered_dicts, stats = self.baseline_engine.filter_findings(
                secret_findings, file_path, source_lines
            )

            # Reconstruct list of SecretMatch objects
            for d in filtered_dicts:
                if "_original_secret" in d:
                    filtered_secrets.append(d["_original_secret"])

            new_count += stats.get("new", 0)
            existing_count += stats.get("existing", 0)
        elif secrets is not None:
            # If secrets passed as empty list, keep it empty
            filtered_secrets = []

        stats = {
            "total": new_count + existing_count,
            "new": new_count,
            "existing": existing_count,
            "resolved": 0,
        }
        return stats, filtered_secrets

    def _extract_block_source(self, block, source_lines: List[str]) -> str:
        min_line = None
        max_line = None
        for stmt in block.statements:
            start = getattr(stmt, "lineno", None)
            if start is None:
                continue
            end = getattr(stmt, "end_lineno", start)
            if min_line is None or start < min_line:
                min_line = start
            if max_line is None or end > max_line:
                max_line = end

        if min_line is None or max_line is None:
            return ""

        min_line = max(min_line, 1)
        max_line = min(max_line, len(source_lines))
        return "\n".join(source_lines[min_line - 1 : max_line])

    def _build_ssa_context(self, block, ssa) -> Dict[str, Any]:
        defs = set()
        uses = set()

        relevant_lines = {
            f.get("line") for f in block.security_findings if f.get("line")
        }
        relevant_vars = set()
        candidates = []

        for stmt in block.statements:
            start = getattr(stmt, "lineno", None)
            end = getattr(stmt, "end_lineno", start)

            is_relevant_stmt = False
            if start is not None and relevant_lines:
                if any(start <= line <= end for line in relevant_lines):
                    is_relevant_stmt = True

            for node in ast.walk(stmt):
                entry = None
                is_def = False

                if isinstance(node, ast.Name):
                    version = ssa.ssa_map.get(node)
                    if not version:
                        continue
                    entry = (node.id, version)
                    if isinstance(node.ctx, ast.Store):
                        is_def = True
                elif isinstance(node, ast.arg):
                    version = ssa.ssa_map.get(node)
                    if not version:
                        continue
                    entry = (node.arg, version)
                    is_def = True

                if entry:
                    if is_relevant_stmt:
                        relevant_vars.add(entry)
                    candidates.append((entry, is_def))

        for entry, is_def in candidates:
            if relevant_vars and entry not in relevant_vars:
                continue

            if is_def:
                defs.add(entry)
            else:
                uses.add(entry)

        phi_nodes = [str(p) for p in block.phi_nodes]
        context = {
            "phi_nodes": phi_nodes,
            "defs": [
                {"name": name, "version": version} for name, version in sorted(defs)
            ],
            "uses": [
                {"name": name, "version": version} for name, version in sorted(uses)
            ],
        }
        return context

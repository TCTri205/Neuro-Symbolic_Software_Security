from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import ast

from src.core.ai.client import LLMClient
from src.core.cfg.callgraph import CallGraph
from src.core.parser.obfuscation import is_binary_extension
from src.core.pipeline.config import PipelineConfig, build_taint_config
from src.core.pipeline.events import (
    EventBus,
    PIPELINE_EVENTS,
    PipelineContext,
    PipelineEventRegistry,
    get_pipeline_event_registry,
    register_pipeline_plugins,
)
from src.core.pipeline.factory import AnalysisFactory, GraphFactory, ScanFactory
from src.core.pipeline.interfaces import (
    AnalysisFactoryPort,
    BaselineEnginePort,
    CFGBuilderPort,
    CallGraphBuilderPort,
    GatekeeperPort,
    GraphBuildPort,
    GraphFactoryPort,
    GraphPersistencePort,
    IRPort,
    LibrarianPort,
    LLMAnalysisPort,
    PromptBuilderPort,
    PrivacyMaskingPort,
    PrivacyMaskerPort,
    RankerPort,
    RouterPort,
    ScanFactoryPort,
    SSAPort,
    SecretScannerPort,
    SemgrepRunnerPort,
    StaticScanPort,
    SyntheticEdgeBuilderPort,
    TaintEnginePort,
    TaintRoutingPort,
    PipelineServiceFactoryPort,
)
from src.core.risk.schema import RankerOutput, RoutingPlan
from src.core.scan.secrets import SecretMatch
from src.core.scan.semgrep import SemgrepRunner
from src.core.taint.engine import TaintConfiguration, TaintFlow
from src.core.telemetry import get_logger
from src.librarian import Librarian


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
            if self.ssa:
                payload["taint_trace_meta"] = self._build_taint_trace_meta()
        if self.ranker_output:
            payload["risk"] = self.ranker_output.model_dump()
        if self.routing:
            payload["routing"] = self.routing.model_dump()
        if self.baseline_stats:
            payload["baseline"] = self.baseline_stats
        return payload

    @staticmethod
    def _node_span(node: ast.AST) -> Dict[str, int]:
        start_line = getattr(node, "lineno", -1)
        start_col = getattr(node, "col_offset", -1)
        end_line = getattr(node, "end_lineno", None)
        end_col = getattr(node, "end_col_offset", None)

        if not isinstance(end_line, int):
            end_line = start_line if isinstance(start_line, int) else -1
        if not isinstance(end_col, int):
            if isinstance(start_col, int) and start_col >= 0:
                end_col = start_col + 1
            else:
                end_col = -1

        return {
            "start_line": start_line if isinstance(start_line, int) else -1,
            "start_col": start_col if isinstance(start_col, int) else -1,
            "end_line": end_line,
            "end_col": end_col,
        }

    def _build_taint_trace_meta(self) -> Dict[str, Any]:
        version_spans: Dict[str, Dict[str, int]] = {}
        if not self.ssa:
            return {"versions": version_spans}

        for version, def_info in self.ssa.version_defs.items():
            def_node = None
            stmt = None
            if isinstance(def_info, tuple) and len(def_info) == 2:
                def_node, stmt = def_info
            else:
                def_node = def_info

            target = None
            if isinstance(stmt, ast.AST):
                target = stmt
            elif isinstance(def_node, ast.AST):
                target = def_node

            if target is None:
                version_spans[version] = {
                    "start_line": -1,
                    "start_col": -1,
                    "end_line": -1,
                    "end_col": -1,
                }
            else:
                version_spans[version] = self._node_span(target)

        return {"versions": version_spans}


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
        semgrep_config: Optional[str] = None,
        config: Optional[PipelineConfig] = None,
        service_factory: Optional[PipelineServiceFactoryPort] = None,
        scan_factory: Optional[ScanFactoryPort] = None,
        graph_factory: Optional[GraphFactoryPort] = None,
        analysis_factory: Optional[AnalysisFactoryPort] = None,
        baseline_engine: Optional[BaselineEnginePort] = None,
        gatekeeper: Optional[GatekeeperPort] = None,
        prompt_builder: Optional[PromptBuilderPort] = None,
        librarian: Optional[LibrarianPort] = None,
        secret_scanner: Optional[SecretScannerPort] = None,
        privacy_masker: Optional[PrivacyMaskerPort] = None,
        graph_persistence: Optional[GraphPersistencePort] = None,
        semgrep_runner: Optional[SemgrepRunnerPort] = None,
        cfg_builder: Optional[CFGBuilderPort] = None,
        call_graph_builder_factory: Optional[
            Callable[[CallGraph], CallGraphBuilderPort]
        ] = None,
        synthetic_builder_factory: Optional[
            Callable[[CallGraph], SyntheticEdgeBuilderPort]
        ] = None,
        taint_engine: Optional[TaintEnginePort] = None,
        ranker: Optional[RankerPort] = None,
        router: Optional[RouterPort] = None,
        event_registry: Optional[PipelineEventRegistry] = None,
        static_scan_service: Optional[StaticScanPort] = None,
        ir_service: Optional[IRPort] = None,
        graph_build_service: Optional[GraphBuildPort] = None,
        ssa_service: Optional[SSAPort] = None,
        llm_service: Optional[LLMAnalysisPort] = None,
        taint_service: Optional[TaintRoutingPort] = None,
        privacy_service: Optional[PrivacyMaskingPort] = None,
    ):
        self.logger = get_logger(__name__)
        self.config = config or PipelineConfig(
            enable_ir=enable_ir,
            enable_docstring_stripping=enable_docstring_stripping,
            baseline_mode=baseline_mode,
            semgrep_config=semgrep_config,
            taint_config=taint_config,
        )
        self.taint_config = build_taint_config(self.config)
        self.librarian = librarian
        if service_factory is not None:
            factory = service_factory
            self.baseline_engine = factory.build_baseline_engine()
            self.baseline_service = factory.build_baseline_service()
            self.gatekeeper = gatekeeper or factory.build_gatekeeper()
            self.static_scan_service = (
                static_scan_service or factory.build_static_scan_service()
            )
            self.ir_service = ir_service or factory.build_ir_service()
            self.graph_build_service = (
                graph_build_service or factory.build_graph_build_service()
            )
            self.ssa_service = ssa_service or factory.build_ssa_service()
            self.llm_service = llm_service or factory.build_llm_service(self.gatekeeper)
            self.privacy_service = privacy_service or factory.build_privacy_service()
            self.taint_service = taint_service or factory.build_taint_service()
        else:
            resolved_librarian = librarian
            if analysis_factory is None and librarian is None:
                resolved_librarian = Librarian()
            self.librarian = resolved_librarian
            scan_factory = scan_factory or ScanFactory(
                self.config,
                self.logger,
                baseline_engine=baseline_engine,
                secret_scanner=secret_scanner,
                semgrep_runner=semgrep_runner,
                semgrep_runner_cls=SemgrepRunner,
            )
            graph_factory = graph_factory or GraphFactory(
                self.config,
                self.logger,
                graph_persistence=graph_persistence,
                cfg_builder=cfg_builder,
                call_graph_builder_factory=call_graph_builder_factory,
                synthetic_builder_factory=synthetic_builder_factory,
            )
            analysis_factory = analysis_factory or AnalysisFactory(
                self.config,
                self.logger,
                gatekeeper=gatekeeper,
                prompt_builder=prompt_builder,
                librarian=resolved_librarian,
                privacy_masker=privacy_masker,
                taint_engine=taint_engine,
                ranker=ranker,
                router=router,
                llm_client_cls=LLMClient,
            )
            self.baseline_engine = scan_factory.build_baseline_engine()
            self.baseline_service = scan_factory.build_baseline_service()
            self.gatekeeper = gatekeeper or analysis_factory.build_gatekeeper()
            self.static_scan_service = (
                static_scan_service or scan_factory.build_static_scan_service()
            )
            self.ir_service = ir_service or graph_factory.build_ir_service()
            self.graph_build_service = (
                graph_build_service or graph_factory.build_graph_build_service()
            )
            self.ssa_service = ssa_service or graph_factory.build_ssa_service()
            self.llm_service = llm_service or analysis_factory.build_llm_service(
                self.gatekeeper
            )
            self.privacy_service = (
                privacy_service or analysis_factory.build_privacy_service()
            )
            self.taint_service = taint_service or analysis_factory.build_taint_service()
        self.event_registry = event_registry

    def _build_event_bus(self) -> EventBus:
        event_bus = EventBus()
        event_bus.register("static_scan", self._handle_static_scan)
        event_bus.register("semgrep", self._handle_semgrep)
        event_bus.register("ir", self._handle_ir)
        event_bus.register("graph_build", self._handle_graph_build)
        event_bus.register("baseline", self._handle_baseline)
        event_bus.register("ssa", self._handle_ssa)
        event_bus.register("taint", self._handle_taint)
        event_bus.register("llm", self._handle_llm)
        event_bus.register("privacy", self._handle_privacy)
        registry = self.event_registry or get_pipeline_event_registry()
        if self.event_registry is None:
            register_pipeline_plugins(registry)
        registry.apply(event_bus)
        return event_bus

    def _handle_static_scan(self, context: PipelineContext) -> None:
        result = context.result
        result.secrets, error = self.static_scan_service.scan_secrets(
            context.source_code
        )
        if error:
            result.errors.append(error)

        is_obfuscated, reasons = self.static_scan_service.check_obfuscation(
            context.source_code
        )
        if is_obfuscated:
            reason_text = ", ".join(reasons) if reasons else "heuristics"
            msg = (
                f"Obfuscated code detected ({reason_text}). "
                "Skipping structural analysis."
            )
            self.logger.warning(msg)
            result.errors.append(msg)
            context.stop()

    def _handle_semgrep(self, context: PipelineContext) -> None:
        result = context.result
        result.semgrep_results, error = self.static_scan_service.scan_semgrep(
            context.file_path
        )
        if error:
            result.errors.append(error)

    def _handle_ir(self, context: PipelineContext) -> None:
        result = context.result
        result.ir, error = self.ir_service.build_ir(
            context.source_code, context.file_path
        )
        if error:
            result.errors.append(error)

    def _handle_graph_build(self, context: PipelineContext) -> None:
        result = context.result
        result.cfg, result.call_graph, error = (
            self.graph_build_service.build_cfg_and_call_graph(
                context.source_code,
                context.file_path,
                result.semgrep_results,
            )
        )
        if error:
            result.errors.append(error)
            context.stop()

    def _handle_baseline(self, context: PipelineContext) -> None:
        if not self.baseline_service or not context.result.cfg:
            return
        try:
            context.result.baseline_stats, context.result.secrets = (
                self.baseline_service.filter_findings(
                    context.result.cfg,
                    context.file_path,
                    context.source_lines,
                    context.result.secrets,
                )
            )
        except Exception as e:
            msg = f"Baseline filtering failed: {e}"
            self.logger.error(msg)
            context.result.errors.append(msg)
            context.stop()

    def _handle_ssa(self, context: PipelineContext) -> None:
        result = context.result
        result.ssa, error = self.ssa_service.transform(result.cfg)
        if error:
            result.errors.append(error)

    def _handle_taint(self, context: PipelineContext) -> None:
        (
            context.result.taint_flows,
            context.result.ranker_output,
            context.result.routing,
            error,
        ) = self.taint_service.analyze(context.result.cfg, context.result.ssa)
        if error:
            context.result.errors.append(error)

    def _handle_llm(self, context: PipelineContext) -> None:
        error = self.llm_service.analyze(
            context.result.cfg,
            context.result.ssa,
            context.source_code,
            context.file_path,
        )
        if error:
            context.result.errors.append(error)

    def _handle_privacy(self, context: PipelineContext) -> None:
        masked_code, mapping, error = self.privacy_service.mask(context.source_code)
        if masked_code is not None:
            context.result.masked_code = masked_code
        if mapping is not None:
            context.result.mask_mapping = mapping
        if error:
            context.result.errors.append(error)

    def analyze_code(
        self, source_code: str, file_path: str = "<unknown>"
    ) -> AnalysisResult:
        result = AnalysisResult(file_path=file_path)
        self.gatekeeper.reset_scan()
        source_lines = source_code.splitlines()
        context = PipelineContext(
            source_code=source_code,
            file_path=file_path,
            result=result,
            source_lines=source_lines,
        )
        event_bus = self._build_event_bus()
        for event_name in PIPELINE_EVENTS:
            event_bus.emit(event_name, context)
            if context.stop_processing:
                break

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

from typing import Any, Dict, List, Optional, Protocol, Tuple

from src.core.risk.schema import RankerOutput, RoutingPlan
from src.core.scan.secrets import SecretMatch
from src.core.taint.engine import TaintFlow


class LLMAnalysisPort(Protocol):
    def analyze(self, cfg, ssa, source: str, file_path: str) -> Optional[str]: ...


class TaintRoutingPort(Protocol):
    def analyze(
        self, cfg, ssa
    ) -> Tuple[
        List[TaintFlow], Optional[RankerOutput], Optional[RoutingPlan], Optional[str]
    ]: ...


class PrivacyMaskingPort(Protocol):
    def mask(
        self, source_code: str
    ) -> Tuple[Optional[str], Optional[Dict[str, str]], Optional[str]]: ...


class StaticScanPort(Protocol):
    def scan_secrets(
        self, source_code: str
    ) -> Tuple[List[SecretMatch], Optional[str]]: ...

    def scan_semgrep(self, file_path: str) -> Tuple[Dict[str, Any], Optional[str]]: ...

    def check_obfuscation(self, source_code: str) -> Tuple[bool, List[str]]: ...


class IRPort(Protocol):
    def build_ir(
        self, source_code: str, file_path: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]: ...


class GraphBuildPort(Protocol):
    def build_cfg_and_call_graph(
        self, source_code: str, file_path: str, semgrep_results: Dict[str, Any]
    ) -> Tuple[Optional[Any], Optional[Any], Optional[str]]: ...


class SSAPort(Protocol):
    def transform(self, cfg) -> Tuple[Optional[Any], Optional[str]]: ...


class GatekeeperPort(Protocol):
    def reset_scan(self) -> None: ...

    def preferred_provider(self) -> str: ...

    def evaluate(self, prompt: str, client) -> Any: ...

    def record_response(self, client, response: Dict[str, Any], decision) -> None: ...


class BaselineEnginePort(Protocol):
    def filter_findings(
        self, findings: List[Dict[str, Any]], file_path: str, source_lines: List[str]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]: ...


class BaselineFilterPort(Protocol):
    def filter_findings(
        self,
        cfg,
        file_path: str,
        source_lines: List[str],
        secrets: Optional[List[SecretMatch]] = None,
    ) -> Tuple[Dict[str, int], List[SecretMatch]]: ...


class PromptBuilderPort(Protocol):
    def build_analysis_prompt(
        self, block, snippet: str, file_path: str, ssa_context: Dict[str, Any]
    ) -> str: ...


class LibrarianPort(Protocol):
    def query(
        self, prompt: str, check_id: str, snippet: str
    ) -> Optional[Dict[str, Any]]: ...

    def store(
        self,
        prompt: str,
        content: str,
        analysis: List[Dict[str, Any]],
        model: str,
        snippet: str,
        check_id: str,
    ) -> None: ...


class SecretScannerPort(Protocol):
    def scan(self, source_code: str) -> List[SecretMatch]: ...


class SemgrepRunnerPort(Protocol):
    def run(self, file_path: str) -> Dict[str, Any]: ...


class GraphPersistencePort(Protocol):
    def load_ir_graph_for_file(self, file_path: str, strict: bool = True): ...

    def save_ir_graph(self, ir_graph, file_path: str) -> None: ...


class PrivacyMaskerPort(Protocol):
    def mask(self, source_code: str) -> Tuple[str, Dict[str, str]]: ...


class TaintEnginePort(Protocol):
    def analyze(self, cfg, ssa_map, taint_config) -> List[TaintFlow]: ...


class RankerPort(Protocol):
    def rank(self, flows: List[TaintFlow]) -> RankerOutput: ...


class RouterPort(Protocol):
    def route(self, ranker_output: RankerOutput) -> RoutingPlan: ...


class CFGBuilderPort(Protocol):
    def build(self, module_name: str, tree) -> Any: ...


class CallGraphBuilderPort(Protocol):
    def extract_definitions(self, tree) -> None: ...

    def build_from_cfg(self, cfg) -> None: ...


class SyntheticEdgeBuilderPort(Protocol):
    def process(self, tree, cfg) -> None: ...


class ScanFactoryPort(Protocol):
    def build_baseline_engine(self) -> Optional[BaselineEnginePort]: ...

    def build_baseline_service(self) -> Optional[BaselineFilterPort]: ...

    def build_static_scan_service(self) -> StaticScanPort: ...


class GraphFactoryPort(Protocol):
    def build_ir_service(self) -> IRPort: ...

    def build_graph_build_service(self) -> GraphBuildPort: ...

    def build_ssa_service(self) -> SSAPort: ...


class AnalysisFactoryPort(Protocol):
    def build_gatekeeper(self) -> GatekeeperPort: ...

    def build_llm_service(self, gatekeeper: GatekeeperPort) -> LLMAnalysisPort: ...

    def build_privacy_service(self) -> PrivacyMaskingPort: ...

    def build_taint_service(self) -> TaintRoutingPort: ...


class PipelineServiceFactoryPort(Protocol):
    def build_baseline_engine(self) -> Optional[BaselineEnginePort]: ...

    def build_baseline_service(self) -> Optional[BaselineFilterPort]: ...

    def build_gatekeeper(self) -> GatekeeperPort: ...

    def build_static_scan_service(self) -> StaticScanPort: ...

    def build_ir_service(self) -> IRPort: ...

    def build_graph_build_service(self) -> GraphBuildPort: ...

    def build_ssa_service(self) -> SSAPort: ...

    def build_llm_service(self, gatekeeper: GatekeeperPort) -> LLMAnalysisPort: ...

    def build_privacy_service(self) -> PrivacyMaskingPort: ...

    def build_taint_service(self) -> TaintRoutingPort: ...

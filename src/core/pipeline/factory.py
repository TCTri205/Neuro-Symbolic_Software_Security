from typing import Callable, Optional, Type

from src.core.ai.client import LLMClient
from src.core.ai.prompts import SecurityPromptBuilder
from src.core.cfg.callgraph import CallGraph, CallGraphBuilder
from src.core.cfg.builder import CFGBuilder
from src.core.cfg.synthetic import SyntheticEdgeBuilder
from src.core.pipeline.config import PipelineConfig, build_taint_config
from src.core.pipeline.gatekeeper import GatekeeperService
from src.core.pipeline.interfaces import (
    AnalysisFactoryPort,
    BaselineEnginePort,
    CFGBuilderPort,
    CallGraphBuilderPort,
    GatekeeperPort,
    GraphFactoryPort,
    GraphPersistencePort,
    LibrarianPort,
    PromptBuilderPort,
    PrivacyMaskerPort,
    RankerPort,
    RouterPort,
    ScanFactoryPort,
    SecretScannerPort,
    SemgrepRunnerPort,
    SyntheticEdgeBuilderPort,
    TaintEnginePort,
)
from src.core.pipeline.services import (
    BaselineFilterService,
    GraphBuildService,
    IRService,
    LLMAnalysisService,
    PrivacyMaskingService,
    SSAService,
    StaticScanService,
    TaintRoutingService,
)
from src.core.privacy.masker import PrivacyMasker
from src.core.risk.ranker import RankerService
from src.core.risk.routing import RoutingService
from src.core.scan.baseline import BaselineEngine
from src.core.scan.semgrep import SemgrepRunner
from src.core.taint.engine import TaintEngine
from src.librarian import Librarian


class ScanFactory:
    def __init__(
        self,
        config: PipelineConfig,
        logger,
        baseline_engine: Optional[BaselineEnginePort] = None,
        secret_scanner: Optional[SecretScannerPort] = None,
        semgrep_runner: Optional[SemgrepRunnerPort] = None,
        semgrep_runner_cls: Type[SemgrepRunner] = SemgrepRunner,
    ) -> None:
        self.config = config
        self.logger = logger
        self.baseline_engine = baseline_engine
        self.secret_scanner = secret_scanner
        self.semgrep_runner = semgrep_runner
        self.semgrep_runner_cls = semgrep_runner_cls

    def build_baseline_engine(self) -> Optional[BaselineEnginePort]:
        if self.baseline_engine is not None:
            return self.baseline_engine
        if self.config.baseline_mode:
            return BaselineEngine()
        return None

    def build_baseline_service(self) -> Optional[BaselineFilterService]:
        engine = self.build_baseline_engine()
        if not engine:
            return None
        return BaselineFilterService(engine, self.logger)

    def build_static_scan_service(self) -> StaticScanService:
        return StaticScanService(
            self.logger,
            semgrep_config=self.config.semgrep_config,
            semgrep_runner_cls=self.semgrep_runner_cls,
            secret_scanner=self.secret_scanner,
            semgrep_runner=self.semgrep_runner,
        )


class GraphFactory:
    def __init__(
        self,
        config: PipelineConfig,
        logger,
        graph_persistence: Optional[GraphPersistencePort] = None,
        cfg_builder: Optional[CFGBuilderPort] = None,
        call_graph_builder_factory: Optional[
            Callable[[CallGraph], CallGraphBuilderPort]
        ] = None,
        synthetic_builder_factory: Optional[
            Callable[[CallGraph], SyntheticEdgeBuilderPort]
        ] = None,
    ) -> None:
        self.config = config
        self.logger = logger
        self.graph_persistence = graph_persistence
        self.cfg_builder = cfg_builder
        self.call_graph_builder_factory = call_graph_builder_factory
        self.synthetic_builder_factory = synthetic_builder_factory

    def build_ir_service(self) -> IRService:
        return IRService(
            self.config.enable_ir,
            self.config.enable_docstring_stripping,
            self.logger,
            persistence=self.graph_persistence,
        )

    def build_graph_build_service(self) -> GraphBuildService:
        return GraphBuildService(
            self.logger,
            cfg_builder=self.cfg_builder or CFGBuilder(),
            call_graph_builder_factory=self.call_graph_builder_factory
            or CallGraphBuilder,
            synthetic_builder_factory=self.synthetic_builder_factory
            or SyntheticEdgeBuilder,
        )

    def build_ssa_service(self) -> SSAService:
        return SSAService(self.logger)


class AnalysisFactory:
    def __init__(
        self,
        config: PipelineConfig,
        logger,
        gatekeeper: Optional[GatekeeperPort] = None,
        prompt_builder: Optional[PromptBuilderPort] = None,
        librarian: Optional[LibrarianPort] = None,
        privacy_masker: Optional[PrivacyMaskerPort] = None,
        taint_engine: Optional[TaintEnginePort] = None,
        ranker: Optional[RankerPort] = None,
        router: Optional[RouterPort] = None,
        llm_client_cls: Type[LLMClient] = LLMClient,
    ) -> None:
        self.config = config
        self.logger = logger
        self.gatekeeper = gatekeeper
        self.prompt_builder = prompt_builder
        self.librarian = librarian
        self.privacy_masker = privacy_masker
        self.taint_engine = taint_engine
        self.ranker = ranker
        self.router = router
        self.llm_client_cls = llm_client_cls

    def build_gatekeeper(self) -> GatekeeperPort:
        return self.gatekeeper or GatekeeperService()

    def build_llm_service(self, gatekeeper: GatekeeperPort) -> LLMAnalysisService:
        prompt_builder = self.prompt_builder or SecurityPromptBuilder()
        librarian = self.librarian or Librarian()
        return LLMAnalysisService(
            prompt_builder,
            librarian,
            gatekeeper,
            self.logger,
            client_cls=self.llm_client_cls,
        )

    def build_privacy_service(self) -> PrivacyMaskingService:
        privacy_masker = self.privacy_masker or PrivacyMasker()
        return PrivacyMaskingService(privacy_masker, self.logger)

    def build_taint_service(self) -> TaintRoutingService:
        taint_config = build_taint_config(self.config)
        return TaintRoutingService(
            self.taint_engine or TaintEngine(),
            self.ranker or RankerService(),
            self.router or RoutingService(),
            taint_config,
            self.logger,
        )


class PipelineServiceFactory:
    def __init__(
        self,
        config: PipelineConfig,
        logger,
        baseline_engine: Optional[BaselineEnginePort] = None,
        gatekeeper: Optional[GatekeeperPort] = None,
        prompt_builder: Optional[PromptBuilderPort] = None,
        librarian: Optional[LibrarianPort] = None,
        secret_scanner: Optional[SecretScannerPort] = None,
        privacy_masker: Optional[PrivacyMaskerPort] = None,
        graph_persistence: Optional[GraphPersistencePort] = None,
        semgrep_runner: Optional[SemgrepRunnerPort] = None,
        semgrep_runner_cls: Type[SemgrepRunner] = SemgrepRunner,
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
        llm_client_cls: Type[LLMClient] = LLMClient,
        scan_factory: Optional[ScanFactoryPort] = None,
        graph_factory: Optional[GraphFactoryPort] = None,
        analysis_factory: Optional[AnalysisFactoryPort] = None,
    ) -> None:
        self.scan_factory = scan_factory or ScanFactory(
            config,
            logger,
            baseline_engine=baseline_engine,
            secret_scanner=secret_scanner,
            semgrep_runner=semgrep_runner,
            semgrep_runner_cls=semgrep_runner_cls,
        )
        self.graph_factory = graph_factory or GraphFactory(
            config,
            logger,
            graph_persistence=graph_persistence,
            cfg_builder=cfg_builder,
            call_graph_builder_factory=call_graph_builder_factory,
            synthetic_builder_factory=synthetic_builder_factory,
        )
        self.analysis_factory = analysis_factory or AnalysisFactory(
            config,
            logger,
            gatekeeper=gatekeeper,
            prompt_builder=prompt_builder,
            librarian=librarian,
            privacy_masker=privacy_masker,
            taint_engine=taint_engine,
            ranker=ranker,
            router=router,
            llm_client_cls=llm_client_cls,
        )

    def build_baseline_engine(self) -> Optional[BaselineEnginePort]:
        return self.scan_factory.build_baseline_engine()

    def build_baseline_service(self) -> Optional[BaselineFilterService]:
        return self.scan_factory.build_baseline_service()

    def build_gatekeeper(self) -> GatekeeperPort:
        return self.analysis_factory.build_gatekeeper()

    def build_static_scan_service(self) -> StaticScanService:
        return self.scan_factory.build_static_scan_service()

    def build_ir_service(self) -> IRService:
        return self.graph_factory.build_ir_service()

    def build_graph_build_service(self) -> GraphBuildService:
        return self.graph_factory.build_graph_build_service()

    def build_ssa_service(self) -> SSAService:
        return self.graph_factory.build_ssa_service()

    def build_llm_service(self, gatekeeper: GatekeeperPort) -> LLMAnalysisService:
        return self.analysis_factory.build_llm_service(gatekeeper)

    def build_privacy_service(self) -> PrivacyMaskingService:
        return self.analysis_factory.build_privacy_service()

    def build_taint_service(self) -> TaintRoutingService:
        return self.analysis_factory.build_taint_service()

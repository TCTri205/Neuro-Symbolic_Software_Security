from typing import List, Optional, Tuple

from src.core.pipeline.interfaces import (
    RankerPort,
    RouterPort,
    TaintEnginePort,
    TaintRoutingPort,
)
from src.core.risk.schema import RankerOutput, RoutingPlan
from src.core.taint.engine import TaintConfiguration, TaintFlow
from src.core.telemetry import MeasureLatency


class TaintRoutingService(TaintRoutingPort):
    def __init__(
        self,
        taint_engine: TaintEnginePort,
        ranker: RankerPort,
        router: RouterPort,
        taint_config: TaintConfiguration,
        logger,
    ) -> None:
        self.taint_engine = taint_engine
        self.ranker = ranker
        self.router = router
        self.taint_config = taint_config
        self.logger = logger

    def analyze(
        self, cfg, ssa
    ) -> Tuple[
        List[TaintFlow], Optional[RankerOutput], Optional[RoutingPlan], Optional[str]
    ]:
        if not cfg or not ssa:
            return [], None, None, None
        try:
            with MeasureLatency("taint_ranking"):
                flows = self.taint_engine.analyze(cfg, ssa.ssa_map, self.taint_config)
                ranker_output = self.ranker.rank(flows)
                routing = self.router.route(ranker_output)
                return flows, ranker_output, routing, None
        except Exception as e:
            msg = f"Taint ranking failed: {e}"
            self.logger.error(msg)
            return [], None, None, msg

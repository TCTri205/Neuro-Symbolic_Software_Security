from typing import Optional, Tuple

from src.core.cfg.ssa.transformer import SSATransformer
from src.core.pipeline.interfaces import SSAPort
from src.core.telemetry import MeasureLatency


class SSAService(SSAPort):
    def __init__(self, logger) -> None:
        self.logger = logger

    def transform(self, cfg) -> Tuple[Optional[SSATransformer], Optional[str]]:
        if not cfg:
            return None, None
        try:
            with MeasureLatency("ssa_transform"):
                ssa = SSATransformer(cfg)
                ssa.analyze()
                return ssa, None
        except Exception as e:
            msg = f"SSA transformation failed: {e}"
            self.logger.error(msg)
            return None, msg

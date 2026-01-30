from typing import Dict, Optional, Tuple

from src.core.pipeline.interfaces import PrivacyMaskerPort, PrivacyMaskingPort
from src.core.telemetry import MeasureLatency


class PrivacyMaskingService(PrivacyMaskingPort):
    def __init__(self, privacy_masker: PrivacyMaskerPort, logger) -> None:
        self.privacy_masker = privacy_masker
        self.logger = logger

    def mask(
        self, source_code: str
    ) -> Tuple[Optional[str], Optional[Dict[str, str]], Optional[str]]:
        try:
            with MeasureLatency("privacy_masking"):
                masked_code, mapping = self.privacy_masker.mask(source_code)
            return masked_code, mapping, None
        except Exception as e:
            msg = f"Privacy masking failed: {e}"
            self.logger.error(msg)
            return None, None, msg

import json
from typing import Any, Dict, Optional

from .base import BaseReporter


class DebugReporter(BaseReporter):
    def generate(
        self,
        results: Dict[str, Any],
        output_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Generate a debug JSON artifact with raw pipeline outputs."""
        metadata_payload = metadata or {}
        payload = {
            "metadata": metadata_payload,
            "results": results,
        }
        if "baseline" in metadata_payload:
            payload["baseline"] = metadata_payload["baseline"]
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

import json
from typing import Dict, Any, Optional

from .base import BaseReporter


class IRReporter(BaseReporter):
    def generate(
        self,
        results: Dict[str, Any],
        output_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Generates a JSON file containing parsed IR per file.
        """
        ir_payload: Dict[str, Any] = {}
        for file_path, file_data in results.items():
            ir_data = file_data.get("ir")
            if ir_data:
                ir_payload[file_path] = ir_data

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"files": ir_payload}, f, indent=2)

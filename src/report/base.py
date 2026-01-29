from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseReporter(ABC):
    @abstractmethod
    def generate(
        self,
        results: Dict[str, Any],
        output_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Generates a report from the pipeline results.

        Args:
            results: The dictionary returned by Pipeline.results
            output_path: The file path to write the report to
            metadata: Optional global metadata (e.g., baseline stats)
        """
        pass

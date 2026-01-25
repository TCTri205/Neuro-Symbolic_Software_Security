from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseReporter(ABC):
    @abstractmethod
    def generate(self, results: Dict[str, Any], output_path: str) -> None:
        """
        Generates a report from the pipeline results.
        
        Args:
            results: The dictionary returned by Pipeline.results
            output_path: The file path to write the report to
        """
        pass

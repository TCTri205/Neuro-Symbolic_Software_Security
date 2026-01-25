import os
import logging
from typing import Dict, Any, List
from .base import BaseReporter
from .markdown import MarkdownReporter
from .sarif import SarifReporter

logger = logging.getLogger(__name__)


class ReportManager:
    """
    Manages the generation of various security reports.
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.reporters: List[BaseReporter] = [MarkdownReporter(), SarifReporter()]

    def generate_all(self, results: Dict[str, Any]) -> List[str]:
        """
        Generates all configured reports.

        Args:
            results: Dictionary mapping file paths to analysis result dicts.

        Returns:
            List of generated file paths.
        """
        if not os.path.exists(self.output_dir):
            try:
                os.makedirs(self.output_dir)
            except OSError as e:
                logger.error(
                    f"Failed to create report directory {self.output_dir}: {e}"
                )
                return []

        generated_files = []

        for reporter in self.reporters:
            try:
                filename = "nsss_report"
                if isinstance(reporter, MarkdownReporter):
                    filename += ".md"
                elif isinstance(reporter, SarifReporter):
                    filename += ".sarif"
                else:
                    # Fallback or skip
                    continue

                output_path = os.path.join(self.output_dir, filename)
                reporter.generate(results, output_path)
                generated_files.append(output_path)
                logger.info(f"Generated report: {output_path}")

            except Exception as e:
                logger.error(
                    f"Failed to generate report with {type(reporter).__name__}: {e}"
                )

        return generated_files

import os
import logging
from typing import Dict, Any, List, Optional
from .base import BaseReporter
from .markdown import MarkdownReporter
from .sarif import SarifReporter
from .ir import IRReporter

logger = logging.getLogger(__name__)


class ReportManager:
    """
    Manages the generation of various security reports.
    """

    def __init__(self, output_dir: str, report_types: Optional[List[str]] = None):
        self.output_dir = output_dir
        self._reporter_registry = {
            "markdown": (MarkdownReporter, ".md"),
            "sarif": (SarifReporter, ".sarif"),
            "ir": (IRReporter, ".ir.json"),
        }
        self.reporters: List[BaseReporter] = self._build_reporters(report_types)

    def _build_reporters(self, report_types: Optional[List[str]]) -> List[BaseReporter]:
        if not report_types:
            selected_types = list(self._reporter_registry.keys())
        else:
            selected_types = [report_type.lower() for report_type in report_types]

        reporters: List[BaseReporter] = []
        for report_type in selected_types:
            registry_entry = self._reporter_registry.get(report_type)
            if not registry_entry:
                logger.warning(f"Unknown report type requested: {report_type}")
                continue
            reporter_cls, _ = registry_entry
            reporters.append(reporter_cls())

        return reporters

    def _report_extension(self, reporter: BaseReporter) -> Optional[str]:
        for reporter_cls, extension in self._reporter_registry.values():
            if isinstance(reporter, reporter_cls):
                return extension
        return None

    def generate_all(
        self, results: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Generates all configured reports.

        Args:
            results: Dictionary mapping file paths to analysis result dicts.
            metadata: Optional global metadata (e.g., baseline stats).

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
                extension = self._report_extension(reporter)
                if not extension:
                    continue
                filename += extension

                output_path = os.path.join(self.output_dir, filename)
                reporter.generate(results, output_path, metadata=metadata)
                generated_files.append(output_path)
                logger.info(f"Generated report: {output_path}")

            except Exception as e:
                logger.error(
                    f"Failed to generate report with {type(reporter).__name__}: {e}"
                )

        return generated_files

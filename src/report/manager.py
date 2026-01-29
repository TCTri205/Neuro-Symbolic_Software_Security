import os
import logging
from typing import Dict, Any, List, Optional
from .base import BaseReporter
from .debug import DebugReporter
from .markdown import MarkdownReporter
from .sarif import SarifReporter
from .ir import IRReporter
from .graph import GraphTraceExporter

logger = logging.getLogger(__name__)


class ReportManager:
    """
    Manages the generation of various security reports.
    """

    def __init__(self, output_dir: str, report_types: Optional[List[str]] = None):
        self.output_dir = output_dir
        self._reporter_registry = {
            "markdown": {
                "cls": MarkdownReporter,
                "extension": ".md",
                "base_name": "nsss_report",
            },
            "debug": {
                "cls": DebugReporter,
                "extension": ".json",
                "base_name": "nsss_debug",
            },
            "sarif": {
                "cls": SarifReporter,
                "extension": ".sarif",
                "base_name": "nsss_report",
            },
            "ir": {
                "cls": IRReporter,
                "extension": ".ir.json",
                "base_name": "nsss_report",
            },
            "graph": {
                "cls": GraphTraceExporter,
                "extension": ".json",
                "base_name": "nsss_graph",
            },
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
            reporter_cls = registry_entry["cls"]
            reporters.append(reporter_cls())

        return reporters

    def _report_extension(self, reporter: BaseReporter) -> Optional[str]:
        for registry_entry in self._reporter_registry.values():
            reporter_cls = registry_entry["cls"]
            if isinstance(reporter, reporter_cls):
                return registry_entry["extension"]
        return None

    def _report_base_name(self, reporter: BaseReporter) -> Optional[str]:
        for registry_entry in self._reporter_registry.values():
            reporter_cls = registry_entry["cls"]
            if isinstance(reporter, reporter_cls):
                return registry_entry["base_name"]
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
        local_metadata = dict(metadata or {})

        graph_report_name = None
        for reporter in self.reporters:
            if isinstance(reporter, GraphTraceExporter):
                graph_report_name = "nsss_graph.json"
                break
        if graph_report_name:
            local_metadata["graph_report_name"] = graph_report_name

        for reporter in self.reporters:
            try:
                base_name = self._report_base_name(reporter) or "nsss_report"
                extension = self._report_extension(reporter)
                if not extension:
                    continue
                filename = f"{base_name}{extension}"

                output_path = os.path.join(self.output_dir, filename)
                reporter.generate(results, output_path, metadata=local_metadata)
                generated_files.append(output_path)
                logger.info(f"Generated report: {output_path}")

            except Exception as e:
                logger.error(
                    f"Failed to generate report with {type(reporter).__name__}: {e}"
                )

        return generated_files

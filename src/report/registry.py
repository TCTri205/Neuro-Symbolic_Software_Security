from typing import Dict, List, Optional, Type

from src.report.base import BaseReporter
from src.report.debug import DebugReporter
from src.report.graph import GraphTraceExporter
from src.report.ir import IRReporter
from src.report.markdown import MarkdownReporter
from src.report.sarif import SarifReporter


class ReporterRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, Dict[str, object]] = {
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

    def register_reporter(
        self, report_type: str, cls: Type[BaseReporter], extension: str, base_name: str
    ) -> None:
        self._registry[report_type.lower()] = {
            "cls": cls,
            "extension": extension,
            "base_name": base_name,
        }

    def list_report_types(self) -> List[str]:
        return list(self._registry.keys())

    def get_reporter(self, report_type: str) -> Optional[BaseReporter]:
        entry = self._registry.get(report_type.lower())
        if not entry:
            return None
        return entry["cls"]()

    def get_extension(self, reporter: BaseReporter) -> Optional[str]:
        for entry in self._registry.values():
            reporter_cls = entry.get("cls")
            if reporter_cls and isinstance(reporter, reporter_cls):
                return entry.get("extension")
        return None

    def get_base_name(self, reporter: BaseReporter) -> Optional[str]:
        for entry in self._registry.values():
            reporter_cls = entry.get("cls")
            if reporter_cls and isinstance(reporter, reporter_cls):
                return entry.get("base_name")
        return None

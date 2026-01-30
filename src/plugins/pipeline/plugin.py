import os
import time
from typing import Any, Dict

from src.core.pipeline.events import PipelineContext, PipelineEventRegistry
from src.core.telemetry import get_logger
from src.core.telemetry.metrics import MetricsCollector
from src.plugins.base import PipelineEventPlugin


class DefaultPipelineEventPlugin(PipelineEventPlugin):
    def __init__(self) -> None:
        self.logger = get_logger(__name__)
        self.metrics = MetricsCollector()

    @property
    def name(self) -> str:
        return "pipeline_default"

    def register(self, registry: PipelineEventRegistry) -> None:
        registry.register("pre_analysis", self._on_pre_analysis)
        registry.register("post_ssa", self._on_post_ssa)

    def _on_pre_analysis(self, context: PipelineContext) -> None:
        self._set_plugin_state(context, "pre_analysis_time", time.time())
        self._apply_gatekeeper(context)
        self.logger.debug("Pre-analysis hook for %s", context.file_path)

    def _on_post_ssa(self, context: PipelineContext) -> None:
        self.logger.debug("Post-SSA hook for %s", context.file_path)
        self._record_latency(context)
        self._emit_report(context)

    def _apply_gatekeeper(self, context: PipelineContext) -> None:
        raw_max_lines = os.getenv("NSSS_PLUGIN_MAX_LINES")
        if not raw_max_lines:
            return

        try:
            max_lines = int(raw_max_lines)
        except ValueError:
            self.logger.warning(
                "Invalid NSSS_PLUGIN_MAX_LINES value: %s", raw_max_lines
            )
            return

        if max_lines <= 0:
            return

        if len(context.source_lines) > max_lines:
            msg = (
                "Plugin gatekeeper: file exceeds max lines "
                f"({len(context.source_lines)} > {max_lines})"
            )
            self._append_error(context, msg)
            context.stop()

    def _record_latency(self, context: PipelineContext) -> None:
        start_time = self._get_plugin_state(context, "pre_analysis_time")
        if not isinstance(start_time, float):
            return
        duration_ms = (time.time() - start_time) * 1000
        self.metrics.track_latency("plugin.pre_to_post_ssa", duration_ms)

    def _emit_report(self, context: PipelineContext) -> None:
        report_dir = os.getenv("NSSS_PLUGIN_REPORT_DIR")
        if not report_dir:
            return

        report_types = os.getenv("NSSS_PLUGIN_REPORT_TYPES")
        report_type_list = None
        if report_types:
            report_type_list = [r.strip().lower() for r in report_types.split(",") if r]

        results = self._build_result_payload(context)
        if not results:
            return

        try:
            from src.report.manager import ReportManager

            manager = ReportManager(report_dir, report_types=report_type_list or None)
            metadata = {"plugin": self.name}
            manager.generate_all(results, metadata=metadata)
        except Exception as exc:
            self.logger.error("Plugin report generation failed: %s", exc)

    def _build_result_payload(self, context: PipelineContext) -> Dict[str, Any]:
        result = context.result
        if hasattr(result, "to_dict"):
            try:
                payload = result.to_dict()
            except Exception as exc:
                self.logger.error("Plugin result serialization failed: %s", exc)
                return {}
        elif isinstance(result, dict):
            payload = result
        else:
            payload = {"error": "Unsupported result type for reporting"}

        return {context.file_path: payload}

    def _set_plugin_state(self, context: PipelineContext, key: str, value: Any) -> None:
        state = getattr(context, "_plugin_state", None)
        if not isinstance(state, dict):
            state = {}
            setattr(context, "_plugin_state", state)
        state[key] = value

    def _get_plugin_state(self, context: PipelineContext, key: str) -> Any:
        state = getattr(context, "_plugin_state", None)
        if not isinstance(state, dict):
            return None
        return state.get(key)

    def _append_error(self, context: PipelineContext, message: str) -> None:
        result = context.result
        if hasattr(result, "errors") and isinstance(result.errors, list):
            result.errors.append(message)
        elif isinstance(result, dict):
            errors = result.get("errors")
            if not isinstance(errors, list):
                errors = []
                result["errors"] = errors
            errors.append(message)

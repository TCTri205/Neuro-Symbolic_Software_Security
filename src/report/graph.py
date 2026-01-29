import json
import logging
from typing import Dict, Any, Optional, List, Tuple

from .base import BaseReporter

logger = logging.getLogger(__name__)


class GraphTraceExporter(BaseReporter):
    def generate(
        self,
        results: Dict[str, Any],
        output_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = self.build_payload(results)
        if not payload.get("traces"):
            logger.warning("No taint traces found for graph output.")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    @staticmethod
    def build_payload(results: Dict[str, Any]) -> Dict[str, Any]:
        traces: List[Dict[str, Any]] = []

        for file_path, file_data in results.items():
            flows = file_data.get("taint_flows", [])
            if not flows:
                continue

            trace_meta = file_data.get("taint_trace_meta", {})
            version_spans = trace_meta.get("versions", {})
            ir_nodes = file_data.get("ir", {}).get("nodes", [])

            for flow in flows:
                trace = GraphTraceExporter._build_trace(
                    file_path=file_path,
                    flow=flow,
                    version_spans=version_spans,
                    ir_nodes=ir_nodes,
                )
                traces.append(trace)

        return {"schema_version": 1, "traces": traces}

    @staticmethod
    def _build_trace(
        file_path: str,
        flow: Dict[str, Any],
        version_spans: Dict[str, Dict[str, int]],
        ir_nodes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        path = list(flow.get("path", []))
        source_label = flow.get("source", "unknown")
        sink_label = flow.get("sink", "unknown")

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        node_id = 1
        source_span = GraphTraceExporter._span_for_version(
            file_path, path, version_spans
        )
        source_ir_ref, source_ir_kind = GraphTraceExporter._match_ir_node(
            source_span, ir_nodes
        )
        nodes.append(
            {
                "id": f"n{node_id}",
                "role": "Source",
                "label": source_label,
                "span": source_span,
                "ir_ref": source_ir_ref,
                "ir_kind": source_ir_kind,
            }
        )

        prev_id = f"n{node_id}"
        node_id += 1

        for ver in path[1:]:
            span = GraphTraceExporter._span_from_version(file_path, ver, version_spans)
            ir_ref, ir_kind = GraphTraceExporter._match_ir_node(span, ir_nodes)
            current_id = f"n{node_id}"
            nodes.append(
                {
                    "id": current_id,
                    "role": "Transform",
                    "label": ver,
                    "span": span,
                    "ir_ref": ir_ref,
                    "ir_kind": ir_kind,
                }
            )
            edges.append({"src": prev_id, "dst": current_id, "kind": "taint"})
            prev_id = current_id
            node_id += 1

        sink_span = GraphTraceExporter._span_from_flow(file_path, flow)
        sink_ir_ref, sink_ir_kind = GraphTraceExporter._match_ir_node(
            sink_span, ir_nodes
        )
        sink_id = f"n{node_id}"
        nodes.append(
            {
                "id": sink_id,
                "role": "Sink",
                "label": sink_label,
                "span": sink_span,
                "ir_ref": sink_ir_ref,
                "ir_kind": sink_ir_kind,
            }
        )
        edges.append({"src": prev_id, "dst": sink_id, "kind": "taint"})

        rule_id = f"taint.{sink_label}"
        sink_line = sink_span.get("start_line", -1)
        finding_id = f"{rule_id}::{file_path}:{sink_line}"

        return {
            "finding_id": finding_id,
            "rule_id": rule_id,
            "file": file_path,
            "nodes": nodes,
            "edges": edges,
            "summary": {
                "source_label": source_label,
                "sink_label": sink_label,
                "path_length": len(nodes),
            },
        }

    @staticmethod
    def _span_for_version(
        file_path: str,
        path: List[str],
        version_spans: Dict[str, Dict[str, int]],
    ) -> Dict[str, Any]:
        if not path:
            return GraphTraceExporter._empty_span(file_path)
        return GraphTraceExporter._span_from_version(file_path, path[0], version_spans)

    @staticmethod
    def _span_from_version(
        file_path: str,
        version: str,
        version_spans: Dict[str, Dict[str, int]],
    ) -> Dict[str, Any]:
        span_data = version_spans.get(version)
        if not span_data:
            return GraphTraceExporter._empty_span(file_path)
        return {
            "file": file_path,
            "start_line": span_data.get("start_line", -1),
            "start_col": span_data.get("start_col", -1),
            "end_line": span_data.get("end_line", -1),
            "end_col": span_data.get("end_col", -1),
        }

    @staticmethod
    def _span_from_flow(file_path: str, flow: Dict[str, Any]) -> Dict[str, Any]:
        span_data = flow.get("sink_span")
        if not span_data:
            return GraphTraceExporter._empty_span(file_path)
        return {
            "file": file_path,
            "start_line": span_data.get("start_line", -1),
            "start_col": span_data.get("start_col", -1),
            "end_line": span_data.get("end_line", -1),
            "end_col": span_data.get("end_col", -1),
        }

    @staticmethod
    def _empty_span(file_path: str) -> Dict[str, Any]:
        return {
            "file": file_path,
            "start_line": -1,
            "start_col": -1,
            "end_line": -1,
            "end_col": -1,
        }

    @staticmethod
    def _match_ir_node(
        span: Dict[str, Any], ir_nodes: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], Optional[str]]:
        if not ir_nodes:
            return None, None
        for node in ir_nodes:
            node_span = node.get("span", {})
            if (
                node_span.get("start_line") == span.get("start_line")
                and node_span.get("start_col") == span.get("start_col")
                and node_span.get("end_line") == span.get("end_line")
                and node_span.get("end_col") == span.get("end_col")
            ):
                return node.get("id"), node.get("kind")
        return None, None

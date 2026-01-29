from src.report.graph import GraphTraceExporter
import tempfile
import os
import json


def test_graph_reporter_schema_and_path_length():
    results = {
        "src/app.py": {
            "taint_flows": [
                {
                    "source": "input",
                    "sink": "exec",
                    "path": ["x_1", "y_1"],
                    "implicit": False,
                    "sink_span": {
                        "start_line": 5,
                        "start_col": 0,
                        "end_line": 5,
                        "end_col": 10,
                    },
                }
            ],
            "taint_trace_meta": {
                "versions": {
                    "x_1": {
                        "start_line": 1,
                        "start_col": 0,
                        "end_line": 1,
                        "end_col": 5,
                    },
                    "y_1": {
                        "start_line": 2,
                        "start_col": 0,
                        "end_line": 2,
                        "end_col": 3,
                    },
                }
            },
        }
    }

    payload = GraphTraceExporter.build_payload(results)

    assert payload["schema_version"] == 1
    assert len(payload["traces"]) == 1

    trace = payload["traces"][0]
    assert trace["summary"]["path_length"] == 3
    assert len(trace["nodes"]) == 3
    assert len(trace["edges"]) == 2

    assert trace["nodes"][0]["role"] == "Source"
    assert trace["nodes"][1]["role"] == "Transform"
    assert trace["nodes"][2]["role"] == "Sink"
    assert trace["nodes"][0]["span"]["file"] == "src/app.py"


def test_graph_reporter_empty_traces():
    payload = GraphTraceExporter.build_payload({"src/app.py": {}})
    assert payload["schema_version"] == 1
    assert payload["traces"] == []


def test_graph_reporter_with_ir_linking():
    results = {
        "src/api.py": {
            "taint_flows": [
                {
                    "source": "request",
                    "sink": "eval",
                    "path": ["req_0"],
                    "sink_span": {
                        "start_line": 10,
                        "start_col": 4,
                        "end_line": 10,
                        "end_col": 20,
                    },
                }
            ],
            "taint_trace_meta": {
                "versions": {
                    "req_0": {
                        "start_line": 2,
                        "start_col": 10,
                        "end_line": 2,
                        "end_col": 15,
                    }
                }
            },
            "ir": {
                "nodes": [
                    {
                        "id": "Name:src/api.py:2:10:0",
                        "kind": "Name",
                        "span": {
                            "start_line": 2,
                            "start_col": 10,
                            "end_line": 2,
                            "end_col": 15,
                        },
                    },
                    {
                        "id": "Call:src/api.py:10:4:0",
                        "kind": "Call",
                        "span": {
                            "start_line": 10,
                            "start_col": 4,
                            "end_line": 10,
                            "end_col": 20,
                        },
                    },
                ]
            },
        }
    }

    payload = GraphTraceExporter.build_payload(results)
    trace = payload["traces"][0]

    # Source node (req_0) should link to Name IR node
    source_node = trace["nodes"][0]
    assert source_node["ir_ref"] == "Name:src/api.py:2:10:0"
    assert source_node["ir_kind"] == "Name"

    # Sink node should link to Call IR node
    sink_node = trace["nodes"][1]
    assert sink_node["ir_ref"] == "Call:src/api.py:10:4:0"
    assert sink_node["ir_kind"] == "Call"


def test_generate_writes_file():
    exporter = GraphTraceExporter()
    results = {"src/test.py": {}}

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "graph.json")
        exporter.generate(results, output_path)

        assert os.path.exists(output_path)
        with open(output_path, "r") as f:
            data = json.load(f)
            assert data["schema_version"] == 1

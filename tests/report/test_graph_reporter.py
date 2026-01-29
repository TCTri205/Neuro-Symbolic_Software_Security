from src.report.graph import GraphTraceExporter


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

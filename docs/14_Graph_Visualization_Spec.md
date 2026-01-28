# 14. Graph Visualization Specification

This document defines the data format and integration points for graph-based visualization of taint paths in NSSS. The goal is to provide a concrete, machine-readable output for UI rendering and debug workflows.

## 1. Goals

* Provide a consistent graph trace format per finding.
* Support rendering in a UI without coupling to a specific frontend library.
* Keep output minimal but sufficient for highlighting source -> sink flows.

## 2. Output Artifacts

Two outputs are required:

1. `nsss_graph.json` (primary, machine-readable)
2. `nsss_graph.svg` (optional, derived visualization for quick viewing)

`nsss_graph.json` is the authoritative source for graph visualization. The SVG can be produced by a renderer or left empty if no renderer is available.

## 3. Graph JSON Schema

Each finding produces a graph trace object:

```json
{
  "finding_id": "PYTHON-SQL-INJECTION-001::src/auth/login.py:15",
  "rule_id": "PYTHON-SQL-INJECTION-001",
  "file": "src/auth/login.py",
  "nodes": [
    {
      "id": "n1",
      "role": "Source",
      "label": "user_input",
      "span": {
        "file": "src/auth/login.py",
        "start_line": 12,
        "start_col": 8,
        "end_line": 12,
        "end_col": 18
      },
      "ir_ref": "Name:src/auth/login.py:12:8:0",
      "ir_kind": "Name"
    },
    {
      "id": "n2",
      "role": "Transform",
      "label": "f-string",
      "span": {
        "file": "src/auth/login.py",
        "start_line": 14,
        "start_col": 12,
        "end_line": 14,
        "end_col": 34
      },
      "ir_ref": "Literal:src/auth/login.py:14:12:0",
      "ir_kind": "Literal"
    },
    {
      "id": "n3",
      "role": "Sink",
      "label": "cursor.execute",
      "span": {
        "file": "src/auth/login.py",
        "start_line": 15,
        "start_col": 4,
        "end_line": 15,
        "end_col": 32
      },
      "ir_ref": "Call:src/auth/login.py:15:4:0",
      "ir_kind": "Call"
    }
  ],
  "edges": [
    {"src": "n1", "dst": "n2", "kind": "taint"},
    {"src": "n2", "dst": "n3", "kind": "taint"}
  ],
  "summary": {
    "source_label": "user_input",
    "sink_label": "cursor.execute",
    "path_length": 3
  }
}
```

### 3.1. Node Roles

* `Source`: Taint source (user input, external data).
* `Transform`: Sanitization or data transformation.
* `Sink`: Sensitive sink (SQL, OS, file, etc.).
* `Intermediate`: Optional internal node type for complex flows.

`ir_kind` should reflect the actual IR `kind` in `docs/07_IR_Schema.md` (e.g., `Name`, `Call`, `Literal`).

### 3.2. IR References

`ir_ref` must match the NSSS IR `Node.id` from `docs/07_IR_Schema.md` when available, to allow cross-linking between graph view and internal graph.

## 4. Integration Points

### 4.1. Reporting

* `nsss_graph.json` is generated alongside `nsss_report.sarif` and `nsss_debug.json`.
* SARIF entries should include a reference to the graph output in `properties`.

```json
"properties": {
  "graph_trace": "reports/nsss_graph.json"
}
```

### 4.2. Debug Output

`nsss_debug.json` can embed the graph trace object directly for debugging purposes.

## 5. Rendering Guidance (Non-binding)

Renderers should:

* Lay out nodes in source -> sink order (left-to-right or top-to-bottom).
* Highlight `Source` and `Sink` nodes with distinct colors.
* Allow hovering or clicking a node to jump to `file:line`.

## 6. Constraints

* Graphs should be trimmed to the minimal path connecting source to sink.
* If multiple sources or sinks exist, create one trace per source-sink pair.
* If no trace can be built, output an empty graph with a warning in debug logs.

## 7. Tasks

* Implement a `GraphTraceExporter` in `src/report/graph.py`.
* Write unit tests for schema correctness and minimal path extraction.

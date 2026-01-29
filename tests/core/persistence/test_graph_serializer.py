import json

import pytest

from src.core.parser.ir import IREdge, IRGraph, IRNode, IRSpan, IRSymbol
from src.core.persistence.graph_serializer import JsonlGraphSerializer


def _sample_graph() -> IRGraph:
    span = IRSpan(
        file="sample.py",
        start_line=1,
        start_col=0,
        end_line=1,
        end_col=10,
    )
    node = IRNode(
        id="Func:sample.py:1:0:0",
        kind="Function",
        span=span,
        parent_id=None,
        scope_id="scope:module",
        attrs={"name": "sample"},
    )
    edge = IREdge.model_validate(
        {"from": node.id, "to": node.id, "type": "flow", "guard_id": None}
    )
    symbol = IRSymbol(
        name="sample",
        kind="function",
        scope_id="scope:module",
        defs=[node.id],
        uses=[],
    )
    return IRGraph(nodes=[node], edges=[edge], symbols=[symbol])


def test_jsonl_graph_round_trip(tmp_path):
    graph = _sample_graph()
    serializer = JsonlGraphSerializer()
    output_path = tmp_path / "graph_v1.jsonl"

    meta = serializer.save(
        graph,
        str(output_path),
        metadata={"project_root": str(tmp_path), "file_path": "sample.py"},
    )

    loaded_graph, loaded_meta = serializer.load(str(output_path))

    assert loaded_meta["type"] == "meta"
    assert loaded_meta["project_root"] == str(tmp_path)
    assert loaded_meta["file_path"] == "sample.py"
    assert meta.version == "1.0"
    assert loaded_graph.model_dump(by_alias=True) == graph.model_dump(by_alias=True)


def test_jsonl_graph_rejects_invalid_meta(tmp_path):
    output_path = tmp_path / "graph_v1.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "type": "meta",
                    "version": "0.9",
                    "timestamp": 1,
                    "project_root": str(tmp_path),
                    "commit_hash": "deadbeef",
                }
            )
            + "\n"
        )

    serializer = JsonlGraphSerializer()
    with pytest.raises(ValueError):
        serializer.load(str(output_path))

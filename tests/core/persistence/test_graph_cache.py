from src.core.parser.ir import IRGraph, IRNode, IRSpan
from src.core.persistence import GraphPersistenceService


def _graph_for(file_path: str) -> IRGraph:
    span = IRSpan(
        file=file_path,
        start_line=1,
        start_col=0,
        end_line=1,
        end_col=1,
    )
    node = IRNode(
        id=f"Func:{file_path}:1:0:0",
        kind="Function",
        span=span,
        parent_id=None,
        scope_id="scope:module",
        attrs={"name": "sample"},
    )
    return IRGraph(nodes=[node], edges=[], symbols=[])


def test_graph_cache_loads_when_fresh(tmp_path):
    sample_path = tmp_path / "sample.py"
    sample_path.write_text("def sample():\n    return 1\n")

    graph = _graph_for(str(sample_path))
    persistence = GraphPersistenceService.get_instance()
    persistence.save_ir_graph(graph, str(sample_path), project_root=str(tmp_path))

    loaded = persistence.load_ir_graph_for_file(
        str(sample_path), project_root=str(tmp_path), strict=True
    )
    assert loaded is not None
    cached_graph, _meta = loaded
    assert cached_graph.model_dump(by_alias=True) == graph.model_dump(by_alias=True)

    sample_path.write_text("def sample():\n    return 2\n")
    stale = persistence.load_ir_graph_for_file(
        str(sample_path), project_root=str(tmp_path), strict=True
    )
    assert stale is None


def test_project_graph_requires_fresh_cache(tmp_path):
    first_path = tmp_path / "first.py"
    second_path = tmp_path / "second.py"
    first_path.write_text("def first():\n    return 1\n")
    second_path.write_text("def second():\n    return 2\n")

    persistence = GraphPersistenceService.get_instance()
    persistence.save_ir_graph(
        _graph_for(str(first_path)), str(first_path), str(tmp_path)
    )
    persistence.save_ir_graph(
        _graph_for(str(second_path)), str(second_path), str(tmp_path)
    )

    loaded = persistence.load_project_graph(str(tmp_path), strict=True)
    assert loaded is not None

    second_path.write_text("def second():\n    return 3\n")
    strict_loaded = persistence.load_project_graph(str(tmp_path), strict=True)
    assert strict_loaded is None

    lax_loaded = persistence.load_project_graph(str(tmp_path), strict=False)
    assert lax_loaded is not None
    graph, _meta = lax_loaded
    assert any(node.span.file.endswith("first.py") for node in graph.nodes)

from src.core.parser.dynamic_tagging import tag_dynamic_areas
from src.core.parser.python_ast import PythonAstParser


def _node_by_id(graph):
    return {node.id: node for node in graph.nodes}


def test_dynamic_tagging_marks_eval_calls() -> None:
    source = """
def handler(user_input):
    return eval(user_input)
"""
    parser = PythonAstParser(source, "dynamic.py", enable_dynamic_tagging=False)
    graph = parser.parse()
    tag_dynamic_areas(graph)

    nodes = _node_by_id(graph)
    eval_calls = [
        node
        for node in graph.nodes
        if node.kind == "Call"
        and nodes.get(node.attrs.get("callee_id"), None)
        and nodes[node.attrs["callee_id"]].kind == "Name"
        and nodes[node.attrs["callee_id"]].attrs.get("name") == "eval"
    ]
    assert eval_calls
    assert "dynamic" in eval_calls[0].attrs.get("tags", [])


def test_dynamic_tagging_marks_callable_results() -> None:
    source = """
def run(obj, method):
    return getattr(obj, method)()
"""
    parser = PythonAstParser(source, "dynamic.py", enable_dynamic_tagging=False)
    graph = parser.parse()
    tag_dynamic_areas(graph)

    nodes = _node_by_id(graph)
    dynamic_calls = [
        node
        for node in graph.nodes
        if node.kind == "Call"
        and nodes.get(node.attrs.get("callee_id"), None)
        and nodes[node.attrs["callee_id"]].kind == "Call"
    ]
    assert dynamic_calls
    assert "dynamic" in dynamic_calls[0].attrs.get("tags", [])


def test_dynamic_tagging_marks_unsupported_nodes() -> None:
    source = """
def build(items):
    return [*items]
"""
    parser = PythonAstParser(source, "dynamic.py", enable_dynamic_tagging=False)
    graph = parser.parse()
    tag_dynamic_areas(graph)

    unsupported = [
        node for node in graph.nodes if node.attrs.get("unsupported") is True
    ]
    assert unsupported
    assert "dynamic" in unsupported[0].attrs.get("tags", [])

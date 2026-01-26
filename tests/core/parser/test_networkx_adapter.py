from src.core.parser.networkx_adapter import build_networkx_graph
from src.core.parser.python_ast import PythonAstParser


def test_build_networkx_graph_preserves_ir() -> None:
    source = """
def foo(x):
    y = x + 1
    return y
"""
    parser = PythonAstParser(source, "sample.py")
    ir = parser.parse()
    graph = build_networkx_graph(ir)

    assert graph.number_of_nodes() == len(ir.nodes)
    assert graph.number_of_edges() == len(ir.edges)

    sample_node = ir.nodes[0]
    node_data = graph.nodes[sample_node.id]
    assert node_data["kind"] == sample_node.kind
    assert node_data["span"]["start_line"] == sample_node.span.start_line

    assert graph.graph["symbols"] == [symbol.model_dump() for symbol in ir.symbols]

    sample_edge = ir.edges[0]
    edge_data = graph.get_edge_data(sample_edge.from_id, sample_edge.to)
    assert any(
        data["type"] == sample_edge.type and data["guard_id"] == sample_edge.guard_id
        for data in edge_data.values()
    )

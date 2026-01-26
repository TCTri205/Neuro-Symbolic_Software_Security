from __future__ import annotations


import networkx as nx

from .ir import IRGraph


def build_networkx_graph(ir: IRGraph) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    for node in ir.nodes:
        graph.add_node(
            node.id,
            kind=node.kind,
            span=node.span.model_dump(),
            parent_id=node.parent_id,
            scope_id=node.scope_id,
            attrs=node.attrs,
        )
    for edge in ir.edges:
        graph.add_edge(
            edge.from_id,
            edge.to,
            type=edge.type,
            guard_id=edge.guard_id,
        )
    graph.graph["symbols"] = [symbol.model_dump() for symbol in ir.symbols]
    return graph

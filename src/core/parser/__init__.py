from .ir import IRGraph, IREdge, IRNode, IRSpan, IRSymbol
from .networkx_adapter import build_networkx_graph
from .python_ast import PythonAstParser
from .alias_resolver import resolve_aliased_calls
from .dynamic_tagging import tag_dynamic_areas

__all__ = [
    "IRGraph",
    "IREdge",
    "IRNode",
    "IRSpan",
    "IRSymbol",
    "PythonAstParser",
    "build_networkx_graph",
    "resolve_aliased_calls",
    "tag_dynamic_areas",
]

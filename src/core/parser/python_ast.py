from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional

from .alias_resolver import resolve_aliased_calls
from .dynamic_tagging import tag_dynamic_areas
from .ir import IREdge, IRGraph, IRNode, IRSpan, IRSymbol, extract_source_code
from .preprocessing import strip_docstrings
from .python_ast_expr import ExpressionVisitorMixin
from .python_ast_stmt import StatementVisitorMixin


class PythonAstParser(StatementVisitorMixin, ExpressionVisitorMixin):
    def __init__(
        self,
        source: str,
        file_path: str,
        max_literal_len: int = 200,
        enable_docstring_stripping: bool = False,
        enable_alias_resolution: bool = True,
        enable_dynamic_tagging: bool = True,
    ) -> None:
        self.source = source
        self.file_path = file_path
        self.graph = IRGraph()
        self._index = 0
        self._scope_index = 0
        self._scope_stack: List[str] = ["scope:module"]
        self._last_stmt_id_by_scope: Dict[str, str] = {}
        self._last_stmt_id_by_block: Dict[str, str] = {}
        self._node_by_id: Dict[str, IRNode] = {}
        self._symbols: Dict[tuple[str, str], Dict[str, Any]] = {}
        self._loop_stack: List[Dict[str, Optional[str]]] = []
        self.max_literal_len = max_literal_len
        self.enable_docstring_stripping = enable_docstring_stripping
        self.enable_alias_resolution = enable_alias_resolution
        self.enable_dynamic_tagging = enable_dynamic_tagging

    def get_source_segment(self, node_id: str) -> str:
        node = self._node_by_id.get(node_id)
        if not node:
            return ""
        return extract_source_code(self.source, node.span)

    def _finalize_symbols(self) -> None:
        self.graph.symbols = [IRSymbol(**symbol) for symbol in self._symbols.values()]

    def parse(self) -> IRGraph:
        module = ast.parse(self.source)
        if self.enable_docstring_stripping:
            strip_docstrings(module)
        self._visit_module(module)
        self._finalize_symbols()
        if self.enable_alias_resolution:
            resolve_aliased_calls(self.graph)
        if self.enable_dynamic_tagging:
            tag_dynamic_areas(self.graph)
        return self.graph

    def _new_id(self, kind: str, node: ast.AST) -> str:
        line = getattr(node, "lineno", -1)
        col = getattr(node, "col_offset", -1)
        idx = self._index
        self._index += 1
        return f"{kind}:{self.file_path}:{line}:{col}:{idx}"

    def _span(self, node: ast.AST) -> IRSpan:
        end_line = getattr(node, "end_lineno", None)
        end_col = getattr(node, "end_col_offset", None)
        return IRSpan(
            file=self.file_path,
            start_line=getattr(node, "lineno", -1),
            start_col=getattr(node, "col_offset", -1),
            end_line=end_line if isinstance(end_line, int) else -1,
            end_col=end_col if isinstance(end_col, int) else -1,
        )

    def _current_scope(self) -> str:
        return self._scope_stack[-1]

    def _new_scope_id(self, label: str) -> str:
        self._scope_index += 1
        return f"{self._current_scope()}:{label}:{self._scope_index}"

    def _add_node(
        self,
        kind: str,
        node: ast.AST,
        parent_id: Optional[str],
        scope_id: Optional[str],
        attrs: Optional[Dict[str, Any]] = None,
    ) -> str:
        node_id = self._new_id(kind, node)
        ir_node = IRNode(
            id=node_id,
            kind=kind,
            span=self._span(node),
            parent_id=parent_id,
            scope_id=scope_id,
            attrs=attrs or {},
        )
        self.graph.add_node(ir_node)
        self._node_by_id[node_id] = ir_node
        return node_id

    def _set_node_attr(self, node_id: str, key: str, value: Any) -> None:
        node = self._node_by_id[node_id]
        node.attrs[key] = value

    def _record_scope_flow(self, stmt_id: str) -> None:
        scope = self._current_scope()
        prev = self._last_stmt_id_by_scope.get(scope)
        if prev:
            self.graph.add_edge(self._edge(prev, stmt_id, "flow", None))
        self._last_stmt_id_by_scope[scope] = stmt_id

    def _record_block_flow(self, block_id: str, stmt_id: str) -> None:
        prev = self._last_stmt_id_by_block.get(block_id)
        if prev:
            self.graph.add_edge(self._edge(prev, stmt_id, "flow", None))
        self._last_stmt_id_by_block[block_id] = stmt_id

    def _edge(
        self, from_id: str, to: str, edge_type: str, guard_id: Optional[str]
    ) -> IREdge:
        return IREdge.model_validate(
            {"from": from_id, "to": to, "type": edge_type, "guard_id": guard_id}
        )

    def _add_symbol_def(
        self, name: str, kind: str, scope_id: str, node_id: str
    ) -> None:
        symbol = self._get_symbol(name, kind, scope_id)
        symbol["defs"].append(node_id)

    def _add_symbol_use(
        self, name: str, kind: str, scope_id: str, node_id: str
    ) -> None:
        symbol = self._get_symbol(name, kind, scope_id)
        symbol["uses"].append(node_id)

    def _get_symbol(self, name: str, kind: str, scope_id: str) -> Dict[str, Any]:
        key = (scope_id, name)
        if key not in self._symbols:
            self._symbols[key] = {
                "name": name,
                "kind": kind,
                "scope_id": scope_id,
                "defs": [],
                "uses": [],
            }
        return self._symbols[key]

    def _extract_target_name(self, target: ast.expr) -> str:
        if isinstance(target, ast.Name):
            return target.id
        return ast.unparse(target)

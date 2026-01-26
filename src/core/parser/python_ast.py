from __future__ import annotations

import ast
import hashlib
from typing import Any, Dict, List, Optional

from .decorator_unroll import extract_all_decorators
from .dynamic_tagging import tag_dynamic_areas
from .embedded_lang_detector import detect_embedded_language
from .ir import IREdge, IRGraph, IRNode, IRSpan, IRSymbol, extract_source_code
from .preprocessing import strip_docstrings


class PythonAstParser:
    def __init__(
        self,
        source: str,
        file_path: str,
        max_literal_len: int = 200,
        enable_docstring_stripping: bool = False,
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
        self.enable_dynamic_tagging = enable_dynamic_tagging

    def get_source_segment(self, node_id: str) -> str:
        """
        Get the original source code segment for a specific node in the IR.
        """
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

    def _visit_module(self, node: ast.Module) -> str:
        module_id = self._add_node(
            "Module", node, parent_id=None, scope_id=self._current_scope(), attrs={}
        )
        body_ids: List[str] = []
        for stmt in node.body:
            stmt_id = self._visit_stmt(stmt, parent_id=module_id)
            if stmt_id:
                body_ids.append(stmt_id)
        self._set_node_attr(module_id, "body_ids", body_ids)
        return module_id

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, parent_id: str
    ) -> str:
        scope_id = f"scope:{node.name}"

        # Extract decorator metadata for unrolling
        decorator_metadata = (
            extract_all_decorators(node.decorator_list) if node.decorator_list else []
        )

        func_id = self._add_node(
            "Function",
            node,
            parent_id=parent_id,
            scope_id=scope_id,
            attrs={
                "name": node.name,
                "params": [arg.arg for arg in node.args.args],
                "returns": ast.unparse(node.returns) if node.returns else None,
                "decorators": [ast.unparse(d) for d in node.decorator_list],
                "decorator_metadata": decorator_metadata,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
            },
        )
        self._scope_stack.append(scope_id)
        for param in node.args.args:
            self._add_symbol_def(param.arg, "param", scope_id, func_id)
        body_ids: List[str] = []
        for stmt in node.body:
            stmt_id = self._visit_stmt(stmt, parent_id=func_id)
            if stmt_id:
                body_ids.append(stmt_id)
        self._scope_stack.pop()
        self._set_node_attr(func_id, "body_ids", body_ids)
        self._record_scope_flow(func_id)
        return func_id

    def _visit_block(
        self, statements: List[ast.stmt], parent_id: str, label: str
    ) -> str:
        block_id = self._add_node(
            "Block",
            statements[0] if statements else ast.Pass(),
            parent_id=parent_id,
            scope_id=self._current_scope(),
            attrs={"label": label, "owner_id": parent_id, "stmt_ids": []},
        )
        stmt_ids: List[str] = []
        for stmt in statements:
            stmt_id = self._visit_stmt(stmt, parent_id=block_id)
            if stmt_id:
                stmt_ids.append(stmt_id)
                self._record_block_flow(block_id, stmt_id)
        self._set_node_attr(block_id, "stmt_ids", stmt_ids)
        return block_id

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

    def _visit_stmt(self, node: ast.stmt, parent_id: str) -> Optional[str]:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return self._visit_function(node, parent_id)
        if isinstance(node, ast.ClassDef):
            scope_id = f"scope:{node.name}"

            # Extract decorator metadata for unrolling
            decorator_metadata = (
                extract_all_decorators(node.decorator_list)
                if node.decorator_list
                else []
            )

            class_id = self._add_node(
                "Class",
                node,
                parent_id=parent_id,
                scope_id=scope_id,
                attrs={
                    "name": node.name,
                    "bases": [ast.unparse(b) for b in node.bases],
                    "keywords": [ast.unparse(k) for k in node.keywords],
                    "decorators": [ast.unparse(d) for d in node.decorator_list],
                    "decorator_metadata": decorator_metadata,
                },
            )
            self._add_symbol_def(node.name, "class", self._current_scope(), class_id)
            self._scope_stack.append(scope_id)
            body_ids: List[str] = []
            for stmt in node.body:
                stmt_id = self._visit_stmt(stmt, parent_id=class_id)
                if stmt_id:
                    body_ids.append(stmt_id)
            self._scope_stack.pop()
            self._set_node_attr(class_id, "body_ids", body_ids)
            self._record_scope_flow(class_id)
            return class_id
        if isinstance(node, ast.Assign):
            value_id = self._visit_expr(node.value, parent_id)
            target_names = [self._extract_target_name(t) for t in node.targets]
            stmt_id = self._add_node(
                "Assign",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"targets": target_names, "value_id": value_id},
            )
            for name in target_names:
                if name:
                    self._add_symbol_def(name, "var", self._current_scope(), stmt_id)
            self._record_scope_flow(stmt_id)
            return stmt_id
        if isinstance(node, ast.AnnAssign):
            value_id = self._visit_expr(node.value, parent_id) if node.value else None
            target_name = self._extract_target_name(node.target)
            annotation = ast.unparse(node.annotation) if node.annotation else None
            stmt_id = self._add_node(
                "Assign",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={
                    "target": target_name,
                    "value_id": value_id,
                    "annotation": annotation,
                },
            )
            if target_name:
                self._add_symbol_def(target_name, "var", self._current_scope(), stmt_id)
            self._record_scope_flow(stmt_id)
            return stmt_id
        if isinstance(node, ast.AugAssign):
            value_id = self._visit_expr(node.value, parent_id)
            target_name = self._extract_target_name(node.target)
            stmt_id = self._add_node(
                "Assign",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={
                    "target": target_name,
                    "op": type(node.op).__name__,
                    "value_id": value_id,
                },
            )
            if target_name:
                self._add_symbol_use(target_name, "var", self._current_scope(), stmt_id)
                self._add_symbol_def(target_name, "var", self._current_scope(), stmt_id)
            self._record_scope_flow(stmt_id)
            return stmt_id
        if isinstance(node, ast.Global):
            for name in node.names:
                self._get_symbol(name, "var", "scope:module")["is_global"] = True
            return None
        if isinstance(node, ast.Nonlocal):
            for name in node.names:
                symbol = self._get_symbol(name, "var", self._current_scope())
                symbol["is_nonlocal"] = True
            return None
        if isinstance(node, ast.Delete):
            target_ids = [self._visit_expr(t, parent_id) for t in node.targets]
            stmt_id = self._add_node(
                "Delete",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"targets": target_ids},
            )
            self._record_scope_flow(stmt_id)
            return stmt_id
        if isinstance(node, ast.Assert):
            test_id = self._visit_expr(node.test, parent_id)
            msg_id = self._visit_expr(node.msg, parent_id) if node.msg else None
            stmt_id = self._add_node(
                "Assert",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"test_id": test_id, "msg_id": msg_id},
            )
            self._record_scope_flow(stmt_id)
            return stmt_id
        if isinstance(node, ast.Return):
            value_id = self._visit_expr(node.value, parent_id) if node.value else None
            stmt_id = self._add_node(
                "Return",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"value_id": value_id},
            )
            self._record_scope_flow(stmt_id)
            return stmt_id
        if isinstance(node, ast.Expr):
            expr_id = self._visit_expr(node.value, parent_id)
            if expr_id:
                self._record_scope_flow(expr_id)
            return expr_id
        if isinstance(node, ast.If):
            test_id = self._visit_expr(node.test, parent_id)
            if_id = self._add_node(
                "If",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"test_id": test_id},
            )
            body_block = self._visit_block(node.body, if_id, "body")
            orelse_block = (
                self._visit_block(node.orelse, if_id, "orelse") if node.orelse else None
            )
            self.graph.add_edge(self._edge(if_id, body_block, "true", test_id))
            if orelse_block:
                self.graph.add_edge(self._edge(if_id, orelse_block, "false", test_id))
            self._record_scope_flow(if_id)
            return if_id
        if isinstance(node, ast.While):
            test_id = self._visit_expr(node.test, parent_id)
            while_id = self._add_node(
                "While",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"test_id": test_id},
            )
            exit_block = self._visit_block(node.orelse, while_id, "exit")
            self._loop_stack.append(
                {
                    "loop_id": while_id,
                    "continue_target": while_id,
                    "break_target": exit_block,
                    "guard_id": test_id,
                }
            )
            body_block = self._visit_block(node.body, while_id, "body")
            self._loop_stack.pop()
            self.graph.add_edge(self._edge(while_id, body_block, "true", test_id))
            self.graph.add_edge(self._edge(while_id, exit_block, "false", test_id))
            self.graph.add_edge(self._edge(body_block, while_id, "flow", test_id))
            self._record_scope_flow(while_id)
            return while_id
        if isinstance(node, (ast.For, ast.AsyncFor)):
            iter_id = self._visit_expr(node.iter, parent_id)
            target_id = self._visit_expr(node.target, parent_id)
            for_id = self._add_node(
                "For",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={
                    "target_id": target_id,
                    "iter_id": iter_id,
                    "is_async": isinstance(node, ast.AsyncFor),
                },
            )
            target_name = self._extract_target_name(node.target)
            if target_name:
                self._add_symbol_def(target_name, "var", self._current_scope(), for_id)
            orelse_block = (
                self._visit_block(node.orelse, for_id, "orelse")
                if node.orelse
                else None
            )
            exit_block = orelse_block or self._visit_block([], for_id, "exit")
            self._loop_stack.append(
                {
                    "loop_id": for_id,
                    "continue_target": for_id,
                    "break_target": exit_block,
                    "guard_id": iter_id,
                }
            )
            body_block = self._visit_block(node.body, for_id, "body")
            self._loop_stack.pop()
            self.graph.add_edge(self._edge(for_id, body_block, "true", iter_id))
            self.graph.add_edge(self._edge(for_id, exit_block, "false", iter_id))
            self.graph.add_edge(self._edge(body_block, for_id, "flow", iter_id))
            self._record_scope_flow(for_id)
            return for_id
        if isinstance(node, ast.Try):
            try_id = self._add_node(
                "Try",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={},
            )
            body_block = self._visit_block(node.body, try_id, "body")
            handler_blocks = []
            for handler in node.handlers:
                handler_block = self._visit_block(handler.body, try_id, "handler")
                handler_blocks.append(handler_block)
            orelse_block = (
                self._visit_block(node.orelse, try_id, "orelse")
                if node.orelse
                else None
            )
            finally_block = (
                self._visit_block(node.finalbody, try_id, "finally")
                if node.finalbody
                else None
            )
            self.graph.add_edge(self._edge(try_id, body_block, "flow", None))
            for handler_block in handler_blocks:
                self.graph.add_edge(
                    self._edge(try_id, handler_block, "exception", try_id)
                )
            if finally_block:
                self.graph.add_edge(self._edge(body_block, finally_block, "flow", None))
                for handler_block in handler_blocks:
                    self.graph.add_edge(
                        self._edge(handler_block, finally_block, "flow", None)
                    )
            if orelse_block:
                self.graph.add_edge(self._edge(body_block, orelse_block, "flow", None))
            self._record_scope_flow(try_id)
            return try_id
        if isinstance(node, ast.Break):
            stmt_id = self._add_node(
                "Break",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={},
            )
            if self._loop_stack:
                loop = self._loop_stack[-1]
                break_target = loop.get("break_target")
                if break_target:
                    self.graph.add_edge(
                        self._edge(stmt_id, break_target, "break", loop.get("guard_id"))
                    )
            self._record_scope_flow(stmt_id)
            return stmt_id
        if isinstance(node, ast.Continue):
            stmt_id = self._add_node(
                "Continue",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={},
            )
            if self._loop_stack:
                loop = self._loop_stack[-1]
                continue_target = loop.get("continue_target")
                if continue_target:
                    self.graph.add_edge(
                        self._edge(
                            stmt_id,
                            continue_target,
                            "continue",
                            loop.get("guard_id"),
                        )
                    )
            self._record_scope_flow(stmt_id)
            return stmt_id
        if isinstance(node, (ast.With, ast.AsyncWith)):
            items = []
            optional_var_names: List[str] = []
            for item in node.items:
                items.append(
                    {
                        "context_expr_id": self._visit_expr(
                            item.context_expr, parent_id
                        ),
                        "optional_vars_id": self._visit_expr(
                            item.optional_vars, parent_id
                        )
                        if item.optional_vars
                        else None,
                    }
                )
                if item.optional_vars:
                    target_name = self._extract_target_name(item.optional_vars)
                    if target_name:
                        self._add_symbol_use(
                            target_name, "var", self._current_scope(), parent_id
                        )
                        optional_var_names.append(target_name)
            with_id = self._add_node(
                "With",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"items": items, "is_async": isinstance(node, ast.AsyncWith)},
            )
            for name in optional_var_names:
                self._add_symbol_def(name, "var", self._current_scope(), with_id)
            body_block = self._visit_block(node.body, with_id, "body")
            self.graph.add_edge(self._edge(with_id, body_block, "flow", None))
            self._record_scope_flow(with_id)
            return with_id
        if isinstance(node, ast.Raise):
            exc_id = self._visit_expr(node.exc, parent_id) if node.exc else None
            cause_id = self._visit_expr(node.cause, parent_id) if node.cause else None
            stmt_id = self._add_node(
                "Raise",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"exc_id": exc_id, "cause_id": cause_id},
            )
            self._record_scope_flow(stmt_id)
            return stmt_id
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
            asnames = [alias.asname for alias in node.names]
            import_id = self._add_node(
                "Import",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"names": names, "asnames": asnames},
            )
            for name, asname in zip(names, asnames):
                sym_name = asname or name
                self._add_symbol_def(
                    sym_name, "import", self._current_scope(), import_id
                )
            self._record_scope_flow(import_id)
            return import_id
        if isinstance(node, ast.ImportFrom):
            names = [alias.name for alias in node.names]
            asnames = [alias.asname for alias in node.names]
            import_id = self._add_node(
                "Import",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={
                    "module": node.module,
                    "names": names,
                    "asnames": asnames,
                    "level": node.level,
                },
            )
            for name, asname in zip(names, asnames):
                sym_name = asname or name
                self._add_symbol_def(
                    sym_name, "import", self._current_scope(), import_id
                )
            self._record_scope_flow(import_id)
            return import_id
        if isinstance(node, ast.Match):
            subject_id = self._visit_expr(node.subject, parent_id)
            match_id = self._add_node(
                "Match",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"subject_id": subject_id, "cases": []},
            )
            cases = []
            for case in node.cases:
                bound_names = []
                self._collect_match_binds(case.pattern, bound_names)
                for name in bound_names:
                    self._add_symbol_def(name, "var", self._current_scope(), match_id)
                guard_id = (
                    self._visit_expr(case.guard, parent_id) if case.guard else None
                )
                body_block = self._visit_block(case.body, match_id, "case")
                cases.append(
                    {
                        "pattern": ast.dump(case.pattern),
                        "binds": bound_names,
                        "guard_id": guard_id,
                        "body_block_id": body_block,
                    }
                )
                self.graph.add_edge(self._edge(match_id, body_block, "flow", guard_id))
            self._set_node_attr(match_id, "cases", cases)
            self._record_scope_flow(match_id)
            return match_id
        return None

    def _visit_comprehension(
        self, node: ast.comprehension, parent_id: str
    ) -> Dict[str, Any]:
        target_id = self._visit_expr(node.target, parent_id)
        iter_id = self._visit_expr(node.iter, parent_id)
        ifs = [self._visit_expr(cond, parent_id) for cond in node.ifs]
        target_name = self._extract_target_name(node.target)
        if target_name and target_id:
            self._add_symbol_def(target_name, "var", self._current_scope(), target_id)
        return {
            "target_id": target_id,
            "iter_id": iter_id,
            "ifs": ifs,
            "is_async": bool(node.is_async),
        }

    def _collect_match_binds(self, pattern: ast.pattern, names: List[str]) -> None:
        if isinstance(pattern, ast.MatchAs):
            if pattern.name:
                names.append(pattern.name)
            if pattern.pattern:
                self._collect_match_binds(pattern.pattern, names)
            return
        if isinstance(pattern, ast.MatchStar):
            if pattern.name:
                names.append(pattern.name)
            return
        if isinstance(pattern, ast.MatchMapping):
            for value_pattern in pattern.patterns:
                self._collect_match_binds(value_pattern, names)
            if pattern.rest:
                names.append(pattern.rest)
            return
        if isinstance(pattern, ast.MatchSequence):
            for sub in pattern.patterns:
                self._collect_match_binds(sub, names)
            return
        if isinstance(pattern, ast.MatchClass):
            for sub in pattern.patterns:
                self._collect_match_binds(sub, names)
            for kw_pattern in pattern.kwd_patterns:
                self._collect_match_binds(kw_pattern, names)
            return
        if isinstance(pattern, ast.MatchOr):
            for sub in pattern.patterns:
                self._collect_match_binds(sub, names)
            return
        return

    def _visit_expr(self, node: ast.expr, parent_id: str) -> Optional[str]:
        if isinstance(node, ast.Name):
            node_id = self._add_node(
                "Name",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"name": node.id, "ctx": type(node.ctx).__name__},
            )
            if isinstance(node.ctx, ast.Load):
                self._add_symbol_use(node.id, "var", self._current_scope(), node_id)
            return node_id
        if isinstance(node, ast.Constant):
            value = node.value
            value_type = type(value).__name__
            attrs: Dict[str, Any] = {"value_type": value_type}

            # Normalize long string literals
            if isinstance(value, str) and len(value) > self.max_literal_len:
                attrs["value"] = value[: self.max_literal_len]
                attrs["value_hash"] = hashlib.sha256(value.encode()).hexdigest()
                attrs["value_truncated"] = True
            else:
                attrs["value"] = value

            # Detect embedded languages in string literals
            if isinstance(value, str):
                embedded_lang, confidence = detect_embedded_language(value)
                if embedded_lang is not None:
                    attrs["embedded_lang"] = embedded_lang
                    attrs["embedded_lang_confidence"] = confidence

            return self._add_node(
                "Literal",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs=attrs,
            )
        if isinstance(node, ast.Lambda):
            params = [arg.arg for arg in node.args.args]
            body_id = self._visit_expr(node.body, parent_id)
            return self._add_node(
                "Lambda",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"params": params, "body_id": body_id},
            )
        if isinstance(node, ast.IfExp):
            test_id = self._visit_expr(node.test, parent_id)
            body_id = self._visit_expr(node.body, parent_id)
            orelse_id = self._visit_expr(node.orelse, parent_id)
            return self._add_node(
                "IfExp",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"test_id": test_id, "body_id": body_id, "orelse_id": orelse_id},
            )
        if isinstance(node, ast.NamedExpr):
            target_id = self._visit_expr(node.target, parent_id)
            value_id = self._visit_expr(node.value, parent_id)
            target_name = self._extract_target_name(node.target)
            node_id = self._add_node(
                "NamedExpr",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={
                    "target_id": target_id,
                    "target_name": target_name,
                    "value_id": value_id,
                },
            )
            if target_name:
                self._add_symbol_def(target_name, "var", self._current_scope(), node_id)
            return node_id
        if isinstance(node, ast.BoolOp):
            values = [self._visit_expr(v, parent_id) for v in node.values]
            return self._add_node(
                "BoolOp",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"op": type(node.op).__name__, "values": values},
            )
        if isinstance(node, ast.UnaryOp):
            operand_id = self._visit_expr(node.operand, parent_id)
            return self._add_node(
                "UnaryOp",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"op": type(node.op).__name__, "operand": operand_id},
            )
        if isinstance(node, ast.List):
            elts = [self._visit_expr(e, parent_id) for e in node.elts]
            return self._add_node(
                "Literal",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"elts": elts, "ctx": type(node.ctx).__name__},
            )
        if isinstance(node, ast.Tuple):
            elts = [self._visit_expr(e, parent_id) for e in node.elts]
            return self._add_node(
                "Literal",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"elts": elts, "ctx": type(node.ctx).__name__},
            )
        if isinstance(node, ast.Dict):
            keys: List[Optional[str]] = []
            for key in node.keys:
                if key is None:
                    keys.append(None)
                else:
                    keys.append(self._visit_expr(key, parent_id))
            values = [self._visit_expr(v, parent_id) for v in node.values]
            return self._add_node(
                "Literal",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"keys": keys, "values": values},
            )
        if isinstance(node, ast.Set):
            elts = [self._visit_expr(e, parent_id) for e in node.elts]
            return self._add_node(
                "Literal",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"elts": elts},
            )
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            outer_scope = self._current_scope()
            comp_scope = self._new_scope_id("comp")
            self._scope_stack.append(comp_scope)
            elt_id = self._visit_expr(node.elt, parent_id)
            generators = [
                self._visit_comprehension(g, parent_id) for g in node.generators
            ]
            self._scope_stack.pop()
            return self._add_node(
                "Literal",
                node,
                parent_id=parent_id,
                scope_id=outer_scope,
                attrs={
                    "elt_id": elt_id,
                    "generators": generators,
                    "comp_scope": comp_scope,
                },
            )
        if isinstance(node, ast.DictComp):
            outer_scope = self._current_scope()
            comp_scope = self._new_scope_id("comp")
            self._scope_stack.append(comp_scope)
            key_id = self._visit_expr(node.key, parent_id)
            value_id = self._visit_expr(node.value, parent_id)
            generators = [
                self._visit_comprehension(g, parent_id) for g in node.generators
            ]
            self._scope_stack.pop()
            return self._add_node(
                "Literal",
                node,
                parent_id=parent_id,
                scope_id=outer_scope,
                attrs={
                    "key_id": key_id,
                    "value_id": value_id,
                    "generators": generators,
                    "comp_scope": comp_scope,
                },
            )
        if isinstance(node, ast.BinOp):
            left_id = self._visit_expr(node.left, parent_id)
            right_id = self._visit_expr(node.right, parent_id)
            return self._add_node(
                "BinOp",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={
                    "op": type(node.op).__name__,
                    "left": left_id,
                    "right": right_id,
                },
            )
        if isinstance(node, ast.Compare):
            left_id = self._visit_expr(node.left, parent_id)
            comparators = [self._visit_expr(c, parent_id) for c in node.comparators]
            return self._add_node(
                "Compare",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={
                    "left": left_id,
                    "ops": [type(op).__name__ for op in node.ops],
                    "comparators": comparators,
                },
            )
        if isinstance(node, ast.Call):
            callee_id = self._visit_expr(node.func, parent_id)
            args = [self._visit_expr(a, parent_id) for a in node.args]
            keywords = [
                {"name": kw.arg, "value_id": self._visit_expr(kw.value, parent_id)}
                for kw in node.keywords
            ]
            return self._add_node(
                "Call",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"callee_id": callee_id, "args": args, "keywords": keywords},
            )
        if isinstance(node, ast.Attribute):
            value_id = self._visit_expr(node.value, parent_id)
            return self._add_node(
                "Attribute",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={
                    "value_id": value_id,
                    "attr": node.attr,
                    "ctx": type(node.ctx).__name__,
                },
            )
        if isinstance(node, ast.Subscript):
            value_id = self._visit_expr(node.value, parent_id)
            slice_id = self._visit_expr(node.slice, parent_id)
            return self._add_node(
                "Subscript",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={
                    "value_id": value_id,
                    "slice_id": slice_id,
                    "ctx": type(node.ctx).__name__,
                },
            )
        if isinstance(node, ast.Await):
            value_id = self._visit_expr(node.value, parent_id)
            return self._add_node(
                "Await",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"value_id": value_id},
            )
        if isinstance(node, ast.Yield):
            value_id = self._visit_expr(node.value, parent_id) if node.value else None
            return self._add_node(
                "Yield",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"value_id": value_id},
            )
        if isinstance(node, ast.YieldFrom):
            value_id = self._visit_expr(node.value, parent_id)
            return self._add_node(
                "Yield",
                node,
                parent_id=parent_id,
                scope_id=self._current_scope(),
                attrs={"value_id": value_id, "is_from": True},
            )

        # Fallback for unsupported expression nodes
        return self._add_node(
            "Literal",
            node,
            parent_id=parent_id,
            scope_id=self._current_scope(),
            attrs={
                "value_type": "Unknown",
                "ast_type": type(node).__name__,
                "unsupported": True,
            },
        )

    def _extract_target_name(self, target: ast.expr) -> str:
        if isinstance(target, ast.Name):
            return target.id
        return ast.unparse(target)

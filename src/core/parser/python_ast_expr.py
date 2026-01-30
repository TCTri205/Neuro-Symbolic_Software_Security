import ast
import hashlib
from typing import Any, Dict, List, Optional

from .embedded_lang_detector import detect_embedded_language


class ExpressionVisitorMixin:
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

            if isinstance(value, str) and len(value) > self.max_literal_len:
                attrs["value"] = value[: self.max_literal_len]
                attrs["value_hash"] = hashlib.sha256(value.encode()).hexdigest()
                attrs["value_truncated"] = True
            else:
                attrs["value"] = value

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

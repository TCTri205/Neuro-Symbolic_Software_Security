import ast
import tokenize
from io import BytesIO
from typing import Optional, Union


class DocstringStripper(ast.NodeTransformer):
    """
    AST Transformer to remove docstrings from Function, Class, and Module nodes.
    Removes the docstring node entirely from the body.
    """

    def _strip_docstring_from_body(self, node: ast.AST) -> None:
        """Helper to remove docstring from a node with a body."""
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            return

        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                # Check if it's really a docstring (first statement)
                # We simply remove it.
                body.pop(0)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        self._strip_docstring_from_body(node)
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(
        self, node: ast.AsyncFunctionDef
    ) -> ast.AsyncFunctionDef:
        self._strip_docstring_from_body(node)
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        self._strip_docstring_from_body(node)
        self.generic_visit(node)
        return node

    def visit_Module(self, node: ast.Module) -> ast.Module:
        self._strip_docstring_from_body(node)
        self.generic_visit(node)
        return node


def strip_docstrings(tree: ast.AST) -> ast.AST:
    """
    Remove docstrings from the AST in-place.
    """
    stripper = DocstringStripper()
    return stripper.visit(tree)


def strip_comments(source: str) -> str:
    """
    Remove comments from Python source code while preserving line numbers and column offsets.
    Comments are replaced with whitespace.
    """
    try:
        # Check if source is bytes or str
        source_bytes = source.encode("utf-8")
        tokens = tokenize.tokenize(BytesIO(source_bytes).readline)

        out_parts = []
        last_lineno = 1
        last_col = 0

        for tok in tokens:
            token_type = tok.type
            token_string = tok.string
            start_line, start_col = tok.start
            end_line, end_col = tok.end

            # Skip encoding token usually at start
            if token_type == tokenize.ENCODING:
                continue

            # Reset column counter if we moved to a new line
            if start_line > last_lineno:
                last_col = 0

            # Handle column gaps (indentation or spaces between tokens)
            if start_col > last_col:
                out_parts.append(" " * (start_col - last_col))

            if token_type == tokenize.COMMENT:
                # Replace comment content with spaces to preserve total length/offsets
                # The length of the comment token string
                comment_len = len(token_string)
                out_parts.append(" " * comment_len)
            else:
                out_parts.append(token_string)

            last_lineno = end_line
            last_col = end_col

        return "".join(out_parts)

    except tokenize.TokenError:
        # Fallback if tokenization fails (e.g., incomplete code)
        return source
    except Exception:
        # Safety fallback
        return source

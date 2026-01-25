from typing import Dict, Set, Tuple
import ast
import builtins


class PrivacyMasker:
    """
    Anonymizes sensitive identifiers (variables, functions, classes, arguments)
    in Python source code while preserving syntax validity.
    """

    def __init__(self, preserve_builtins: bool = True):
        self.preserve_builtins = preserve_builtins
        self.builtin_names = set(dir(builtins)) if preserve_builtins else set()
        # Add common naming conventions to preserve (optional, can be expanded)
        self.preserved_names = {"self", "cls", "args", "kwargs", "_"}

    def mask(self, source_code: str) -> Tuple[str, Dict[str, str]]:
        """
        Masks identifiers in the source code.

        Returns:
            Tuple[str, Dict[str, str]]: (masked_code, mapping_dict)
            mapping_dict maps masked_name -> original_name
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            # Fallback or raise? For now, raise to let caller handle invalid code
            raise

        transformer = Anonymizer(self.builtin_names | self.preserved_names)
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        masked_code = ast.unparse(new_tree)

        # Invert the mapping for restoration: masked -> original
        return masked_code, transformer.mapping


class Anonymizer(ast.NodeTransformer):
    def __init__(self, preserved: Set[str]):
        self.preserved = preserved
        self.mapping: Dict[str, str] = {}  # masked -> original
        self.original_to_masked: Dict[str, str] = {}  # original -> masked
        self.counters = {"var": 0, "func": 0, "class": 0, "arg": 0}

    def _get_masked_name(self, original: str, prefix: str) -> str:
        if original in self.preserved:
            return original

        if original in self.original_to_masked:
            return self.original_to_masked[original]

        self.counters[prefix] += 1
        masked = f"{prefix}_{self.counters[prefix]}"

        self.original_to_masked[original] = masked
        self.mapping[masked] = original
        return masked

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.preserved:
            return node

        # Don't mask True, False, None (handled by keywords usually, but Name in older python or contexts)
        if node.id in {"True", "False", "None"}:
            return node

        new_id = self._get_masked_name(node.id, "var")
        return ast.copy_location(ast.Name(id=new_id, ctx=node.ctx), node)

    def visit_FunctionDef(self, node):
        # Don't mask magic methods like __init__
        if node.name.startswith("__") and node.name.endswith("__"):
            self.generic_visit(node)
            return node

        new_name = self._get_masked_name(node.name, "func")
        node.name = new_name
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node):
        if node.name.startswith("__") and node.name.endswith("__"):
            self.generic_visit(node)
            return node

        new_name = self._get_masked_name(node.name, "func")
        node.name = new_name
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node):
        new_name = self._get_masked_name(node.name, "class")
        node.name = new_name
        self.generic_visit(node)
        return node

    def visit_arg(self, node):
        if node.arg in {"self", "cls"}:
            return node

        new_name = self._get_masked_name(node.arg, "arg")
        node.arg = new_name
        return node

    # Handle attributes? e.g. obj.prop
    # Masking attributes is risky because methods belong to external libs.
    # For now, SAFE APPROACH: Do NOT mask attributes (node.attr) in Attribute nodes.
    # Only mask the object itself (node.value).

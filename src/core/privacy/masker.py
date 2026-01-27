from typing import Dict, Set, Tuple, Optional
import ast
import builtins


class PrivacyMasker:
    """
    Anonymizes sensitive identifiers (variables, functions, classes, arguments)
    in Python source code while preserving syntax validity.
    Supports typed masking (USER_STR_1, INT_1) and taint-aware masking.
    """

    def __init__(self, preserve_builtins: bool = True):
        self.preserve_builtins = preserve_builtins
        self.builtin_names = set(dir(builtins)) if preserve_builtins else set()
        # Add common naming conventions to preserve (optional, can be expanded)
        self.preserved_names = {"self", "cls", "args", "kwargs", "_"}

    def mask(
        self, source_code: str, sensitive_vars: Optional[Set[str]] = None
    ) -> Tuple[str, Dict[str, str]]:
        """
        Masks identifiers in the source code.

        Args:
            source_code: The Python source code.
            sensitive_vars: Set of variable names to be treated as user/tainted input.

        Returns:
            Tuple[str, Dict[str, str]]: (masked_code, mapping_dict)
            mapping_dict maps masked_name -> original_name
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            # Fallback or raise? For now, raise to let caller handle invalid code
            raise

        transformer = Anonymizer(
            self.builtin_names | self.preserved_names, sensitive_vars or set()
        )
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        masked_code = ast.unparse(new_tree)

        # Invert the mapping for restoration: masked -> original
        return masked_code, transformer.mapping


class Anonymizer(ast.NodeTransformer):
    def __init__(self, preserved: Set[str], sensitive_vars: Set[str]):
        self.preserved = preserved
        self.sensitive_vars = sensitive_vars
        self.mapping: Dict[str, str] = {}  # masked -> original
        self.original_to_masked: Dict[str, str] = {}  # original -> masked
        # Counters for each prefix type
        self.counters: Dict[str, int] = {}
        # Keep track of inferred types for names: name -> prefix
        self.name_types: Dict[str, str] = {}

    def _infer_prefix_from_annotation(self, annotation: ast.AST) -> str:
        """Heuristic to infer type prefix from AST annotation."""
        if not annotation:
            return "VAR"

        type_name = "VAR"
        if isinstance(annotation, ast.Name):
            type_name = annotation.id
        elif isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            type_name = annotation.value
        # Handle List[str], etc.
        elif isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name):
                type_name = annotation.value.id

        type_map = {
            "str": "STR",
            "int": "INT",
            "float": "FLOAT",
            "bool": "BOOL",
            "list": "LIST",
            "List": "LIST",
            "dict": "DICT",
            "Dict": "DICT",
            "set": "SET",
            "Set": "SET",
            "tuple": "TUPLE",
            "Tuple": "TUPLE",
        }
        return type_map.get(type_name, "OBJ")

    def _infer_prefix_from_value(self, value: ast.AST) -> str:
        """Heuristic to infer type prefix from value assignment."""
        if isinstance(value, ast.Constant):
            if isinstance(value.value, str):
                return "STR"
            if isinstance(value.value, int):
                return "INT"
            if isinstance(value.value, float):
                return "FLOAT"
            if isinstance(value.value, bool):
                return "BOOL"
        elif isinstance(value, ast.List):
            return "LIST"
        elif isinstance(value, ast.Dict):
            return "DICT"
        elif isinstance(value, ast.Set):
            return "SET"
        elif isinstance(value, ast.Tuple):
            return "TUPLE"
        return "VAR"

    def _get_masked_name(self, original: str, prefix: str) -> str:
        if original in self.preserved:
            return original

        if original in self.original_to_masked:
            return self.original_to_masked[original]

        # Check if we have an inferred type stored
        if original in self.name_types:
            prefix = self.name_types[original]

        # Check for taint/sensitive
        if original in self.sensitive_vars:
            if not prefix.startswith("USER_"):
                prefix = f"USER_{prefix}"

        # Ensure prefix matches convention (UPPER CASE)
        prefix = prefix.upper()

        if prefix not in self.counters:
            self.counters[prefix] = 0
        self.counters[prefix] += 1

        masked = f"{prefix}_{self.counters[prefix]}"

        self.original_to_masked[original] = masked
        self.mapping[masked] = original
        return masked

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.preserved:
            return node

        # Don't mask True, False, None
        if node.id in {"True", "False", "None"}:
            return node

        # If it's a store (assignment), try to see if we can infer type?
        # But visit_Name is generic.
        # Logic is moved to visit_Assign/AnnAssign for type inference.

        # Default fallback prefix
        new_id = self._get_masked_name(node.id, "VAR")
        return ast.copy_location(ast.Name(id=new_id, ctx=node.ctx), node)

    def visit_FunctionDef(self, node):
        if node.name.startswith("__") and node.name.endswith("__"):
            self.generic_visit(node)
            return node

        new_name = self._get_masked_name(node.name, "FUNC")
        node.name = new_name
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node):
        if node.name.startswith("__") and node.name.endswith("__"):
            self.generic_visit(node)
            return node

        new_name = self._get_masked_name(node.name, "FUNC")
        node.name = new_name
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node):
        new_name = self._get_masked_name(node.name, "CLASS")
        node.name = new_name
        self.generic_visit(node)
        return node

    def visit_arg(self, node):
        if node.arg in {"self", "cls"}:
            return node

        # Infer type from annotation
        prefix = "ARG"  # Default for arguments if no type
        if node.annotation:
            prefix = self._infer_prefix_from_annotation(node.annotation)

        # Store inferred type for future usage
        self.name_types[node.arg] = prefix

        new_name = self._get_masked_name(node.arg, prefix)
        node.arg = new_name
        return node

    def visit_AnnAssign(self, node):
        # target: annotation = value
        if isinstance(node.target, ast.Name):
            prefix = self._infer_prefix_from_annotation(node.annotation)
            self.name_types[node.target.id] = prefix

            # Now mask the target
            # Note: visit_Name would be called on node.target if we used generic_visit on node.target
            # But AnnAssign has 'target' which is a Name node (or Attribute/Subscript).

            # We process target manually to ensure we use the type
            if isinstance(node.target, ast.Name):
                node.target.id = self._get_masked_name(node.target.id, prefix)

        # Visit value and annotation (to mask things inside them)
        if node.value:
            self.visit(node.value)
        # We usually don't mask annotations themselves (types), or do we?
        # If the type is a custom class, maybe. But let's leave annotations alone for now.
        return node

    def visit_Assign(self, node):
        # targets = value
        # Try to infer type from value
        prefix = self._infer_prefix_from_value(node.value)

        for target in node.targets:
            if isinstance(target, ast.Name):
                # If we haven't seen this name before, or if we want to update type?
                # Only update if current prefix is VAR (default)
                if (
                    target.id not in self.name_types
                    or self.name_types[target.id] == "VAR"
                ):
                    self.name_types[target.id] = prefix

                # We need to mask the target.
                # visit_Name will handle it, but we want to ensure _get_masked_name sees the type.
                # However, visit_Name calls _get_masked_name(node.id, "VAR").
                # Inside _get_masked_name, we check self.name_types.
                pass

        self.generic_visit(node)
        return node

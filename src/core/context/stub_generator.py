"""
Stub Generator for Missing Imports.

Generates .pyi stub files for external modules that lack type information.
This is particularly useful for:
- C-extensions (numpy, torch, etc.)
- Obfuscated code
- Third-party libraries without stubs
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

# Python stdlib modules that should not have stubs generated
STDLIB_MODULES = set(sys.stdlib_module_names)


class StubGenerator:
    """Generate type stub files (.pyi) for missing imports."""

    def __init__(self, output_dir: str):
        """
        Initialize stub generator.

        Args:
            output_dir: Directory to write stub files to
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._generated_stubs: set[str] = set()

    def generate_stub(
        self,
        module_name: str,
        imports: List[str],
        is_c_extension: bool = False,
        known_signatures: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """
        Generate a stub file for a module.

        Args:
            module_name: Name of the module (e.g., "mypackage.submodule")
            imports: List of imported names from the module
            is_c_extension: Whether this is a C-extension module
            known_signatures: Optional dict mapping names to known type signatures

        Returns:
            Path to generated stub file, or None if skipped
        """
        # Skip stdlib modules
        if module_name.split(".")[0] in STDLIB_MODULES:
            return None

        # Check if already generated
        if module_name in self._generated_stubs:
            return str(self._get_stub_path(module_name))

        # Create package structure
        stub_path = self._create_package_structure(module_name)

        # Generate stub content
        content = self._generate_stub_content(
            module_name=module_name,
            imports=imports,
            is_c_extension=is_c_extension,
            known_signatures=known_signatures or {},
        )

        # Write stub file
        with open(stub_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Mark as generated
        self._generated_stubs.add(module_name)

        return str(stub_path)

    def _get_stub_path(self, module_name: str) -> Path:
        """Get the path where a stub file should be written."""
        parts = module_name.split(".")
        if len(parts) == 1:
            # Top-level module: module.pyi
            return self.output_dir / f"{module_name}.pyi"
        else:
            # Nested module: package/subpackage/module.pyi
            package_path = self.output_dir.joinpath(*parts[:-1])
            return package_path / f"{parts[-1]}.pyi"

    def _create_package_structure(self, module_name: str) -> Path:
        """
        Create package directory structure with __init__.pyi files.

        Args:
            module_name: Full module name (e.g., "mypackage.submodule.core")

        Returns:
            Path to the stub file
        """
        parts = module_name.split(".")
        stub_path = self._get_stub_path(module_name)

        # Create parent directories
        stub_path.parent.mkdir(parents=True, exist_ok=True)

        # Create __init__.pyi for each package level
        if len(parts) > 1:
            current_path = self.output_dir
            for part in parts[:-1]:
                current_path = current_path / part
                init_file = current_path / "__init__.pyi"
                if not init_file.exists():
                    init_file.write_text("# Package stub\n", encoding="utf-8")

        return stub_path

    def _generate_stub_content(
        self,
        module_name: str,
        imports: List[str],
        is_c_extension: bool,
        known_signatures: Dict[str, str],
    ) -> str:
        """
        Generate the content of a stub file.

        Args:
            module_name: Module name
            imports: List of imported names
            is_c_extension: Whether this is a C-extension
            known_signatures: Known type signatures

        Returns:
            Stub file content
        """
        lines = []

        # Header
        lines.append(f'"""Stub file for {module_name}."""')
        lines.append("")

        # Import typing for fallback types
        if is_c_extension or not known_signatures:
            lines.append("from typing import Any")
            lines.append("")

        # Generate stubs for each imported name
        for name in imports:
            if name in known_signatures:
                # Use known signature
                lines.append(known_signatures[name])
            else:
                # Generate generic stub
                if is_c_extension:
                    # C-extensions: use Any for safety
                    if name[0].isupper():  # Likely a class
                        lines.append(f"class {name}:")
                        lines.append(
                            "    def __init__(self, *args: Any, **kwargs: Any) -> None: ..."
                        )
                    else:  # Likely a function
                        lines.append(
                            f"def {name}(*args: Any, **kwargs: Any) -> Any: ..."
                        )
                else:
                    # Regular module: generate basic stubs
                    if name[0].isupper():  # Likely a class
                        lines.append(f"class {name}:")
                        lines.append("    ...")
                    else:  # Likely a function
                        lines.append(f"def {name}(*args, **kwargs): ...")

            lines.append("")

        return "\n".join(lines)

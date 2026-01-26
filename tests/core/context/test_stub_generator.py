"""
Tests for stub generation functionality.

Stub generation creates .pyi files for missing imports to support static analysis
when type information is unavailable (e.g., C-extensions, obfuscated code).
"""

import os
import tempfile
from pathlib import Path


from src.core.context.stub_generator import StubGenerator


class TestStubGenerator:
    """Test stub generation for missing imports."""

    def test_generate_basic_stub(self):
        """Should generate a basic stub file with common types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = StubGenerator(output_dir=tmpdir)

            # Generate stub for a missing module
            stub_path = generator.generate_stub(
                module_name="missing_module", imports=["SomeClass", "some_function"]
            )

            # Verify stub file was created
            assert os.path.exists(stub_path)
            assert stub_path.endswith("missing_module.pyi")

            # Verify stub content
            with open(stub_path, "r", encoding="utf-8") as f:
                content = f.read()

            assert "class SomeClass:" in content
            assert "def some_function(" in content

    def test_generate_stub_for_c_extension(self):
        """Should generate stub for C-extension with fallback types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = StubGenerator(output_dir=tmpdir)

            # Generate stub for a C-extension module
            stub_path = generator.generate_stub(
                module_name="numpy.core._multiarray_umath",
                imports=["ndarray", "dtype"],
                is_c_extension=True,
            )

            # Verify stub was created
            assert os.path.exists(stub_path)

            # Verify content includes typing.Any fallback
            with open(stub_path, "r", encoding="utf-8") as f:
                content = f.read()

            assert "from typing import Any" in content
            # C-extension stubs should use Any for safety
            assert "Any" in content

    def test_generate_stub_with_known_signatures(self):
        """Should use known signatures when available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = StubGenerator(output_dir=tmpdir)

            # Provide known signatures
            signatures = {
                "get_user": "def get_user(user_id: int) -> dict: ...",
                "User": "class User:\n    id: int\n    name: str",
            }

            stub_path = generator.generate_stub(
                module_name="user_service",
                imports=["get_user", "User"],
                known_signatures=signatures,
            )

            # Verify known signatures were used
            with open(stub_path, "r", encoding="utf-8") as f:
                content = f.read()

            assert "def get_user(user_id: int) -> dict: ..." in content
            assert "class User:" in content
            assert "id: int" in content

    def test_generate_stub_creates_package_structure(self):
        """Should create __init__.pyi for package stubs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = StubGenerator(output_dir=tmpdir)

            # Generate stub for a nested module
            stub_path = generator.generate_stub(
                module_name="mypackage.submodule.core", imports=["MyClass"]
            )

            # Verify package structure
            package_dir = Path(tmpdir) / "mypackage" / "submodule"
            assert package_dir.exists()

            # Verify __init__.pyi files
            assert (Path(tmpdir) / "mypackage" / "__init__.pyi").exists()
            assert (package_dir / "__init__.pyi").exists()
            assert stub_path == str(package_dir / "core.pyi")

    def test_skip_stdlib_modules(self):
        """Should not generate stubs for stdlib modules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = StubGenerator(output_dir=tmpdir)

            # Try to generate stub for stdlib module
            stub_path = generator.generate_stub(module_name="os", imports=["path"])

            # Should return None (skipped)
            assert stub_path is None

    def test_deduplicate_stubs(self):
        """Should not regenerate existing stubs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = StubGenerator(output_dir=tmpdir)

            # Generate stub first time
            stub_path_1 = generator.generate_stub(
                module_name="custom_module", imports=["Foo"]
            )

            # Get creation time
            mtime_1 = os.path.getmtime(stub_path_1)

            # Try to generate again
            stub_path_2 = generator.generate_stub(
                module_name="custom_module", imports=["Foo", "Bar"]
            )

            # Should return existing path without regenerating
            assert stub_path_1 == stub_path_2
            mtime_2 = os.path.getmtime(stub_path_2)
            assert mtime_1 == mtime_2  # File not modified

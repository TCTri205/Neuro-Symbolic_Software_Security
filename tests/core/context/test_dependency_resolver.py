"""
Tests for DependencyResolver.

The DependencyResolver parses dependency files (requirements.txt, pyproject.toml, lock files)
and extracts package names with specific versions.
"""

import tempfile
from pathlib import Path


from src.core.context.dependency_resolver import DependencyResolver


class TestDependencyResolver:
    """Test DependencyResolver functionality."""

    def test_parse_requirements_txt_basic(self):
        """Test parsing basic requirements.txt with pinned versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create requirements.txt
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text(
                "Flask==2.0.1\n"
                "requests>=2.25.0\n"
                "Django~=3.2.0\n"
                "# Comment line\n"
                "pytest  # inline comment\n"
            )

            resolver = DependencyResolver(tmpdir)
            deps = resolver.resolve()

            # Verify parsed dependencies
            assert len(deps) == 4
            dep_dict = {d.name: d for d in deps}

            # Flask with exact version
            assert dep_dict["Flask"].name == "Flask"
            assert dep_dict["Flask"].version == "2.0.1"
            assert dep_dict["Flask"].specifier == "=="

            # requests with minimum version
            assert dep_dict["requests"].version == "2.25.0"
            assert dep_dict["requests"].specifier == ">="

            # Django with compatible release
            assert dep_dict["Django"].version == "3.2.0"
            assert dep_dict["Django"].specifier == "~="

            # pytest without version
            assert dep_dict["pytest"].version is None
            assert dep_dict["pytest"].specifier is None

    def test_parse_pyproject_toml_poetry(self):
        """Test parsing pyproject.toml (Poetry format)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create pyproject.toml
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text(
                """
[tool.poetry]
name = "test-project"
version = "1.0.0"

[tool.poetry.dependencies]
python = "^3.10"
Flask = "2.0.1"
requests = "^2.25.0"

[tool.poetry.dev-dependencies]
pytest = "^7.0.0"
"""
            )

            resolver = DependencyResolver(tmpdir)
            deps = resolver.resolve()

            # Verify main dependencies (excluding python)
            dep_dict = {d.name: d for d in deps if d.name != "python"}
            assert "Flask" in dep_dict
            assert "requests" in dep_dict
            assert "pytest" in dep_dict

            # Flask should have exact version
            assert dep_dict["Flask"].version == "2.0.1"

    def test_parse_pyproject_toml_pep621(self):
        """Test parsing pyproject.toml (PEP 621 format)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create pyproject.toml
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text(
                """
[project]
name = "test-project"
version = "1.0.0"
dependencies = [
    "Flask==2.0.1",
    "requests>=2.25.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
]
"""
            )

            resolver = DependencyResolver(tmpdir)
            deps = resolver.resolve()

            dep_dict = {d.name: d for d in deps}
            assert "Flask" in dep_dict
            assert "requests" in dep_dict
            assert "pytest" in dep_dict

            assert dep_dict["Flask"].version == "2.0.1"
            assert dep_dict["Flask"].specifier == "=="

    def test_parse_poetry_lock(self):
        """Test parsing poetry.lock for exact resolved versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create poetry.lock
            lock_file = Path(tmpdir) / "poetry.lock"
            lock_file.write_text(
                """
[[package]]
name = "Flask"
version = "2.0.1"
description = "A simple framework"

[[package]]
name = "requests"
version = "2.28.1"
description = "HTTP library"
"""
            )

            resolver = DependencyResolver(tmpdir)
            deps = resolver.resolve()

            dep_dict = {d.name: d for d in deps}
            assert len(dep_dict) >= 2

            # Lock files have exact versions
            assert dep_dict["Flask"].version == "2.0.1"
            assert dep_dict["Flask"].specifier == "=="
            assert dep_dict["requests"].version == "2.28.1"
            assert dep_dict["requests"].specifier == "=="

    def test_parse_pipfile_lock(self):
        """Test parsing Pipfile.lock for exact resolved versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Pipfile.lock
            lock_file = Path(tmpdir) / "Pipfile.lock"
            lock_file.write_text(
                """
{
    "default": {
        "flask": {
            "version": "==2.0.1"
        },
        "requests": {
            "version": "==2.28.1"
        }
    },
    "develop": {
        "pytest": {
            "version": "==7.2.0"
        }
    }
}
"""
            )

            resolver = DependencyResolver(tmpdir)
            deps = resolver.resolve()

            dep_dict = {d.name: d for d in deps}
            assert len(dep_dict) >= 3

            # Verify case-insensitive matching (flask -> Flask)
            assert "flask" in dep_dict or "Flask" in dep_dict
            flask_dep = dep_dict.get("flask") or dep_dict.get("Flask")
            assert flask_dep.version == "2.0.1"

    def test_priority_lock_over_requirements(self):
        """Test that lock files take priority over requirements.txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create requirements.txt with version range
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("Flask>=2.0.0")

            # Create poetry.lock with exact version
            lock_file = Path(tmpdir) / "poetry.lock"
            lock_file.write_text(
                """
[[package]]
name = "Flask"
version = "2.0.3"
"""
            )

            resolver = DependencyResolver(tmpdir)
            deps = resolver.resolve()

            dep_dict = {d.name: d for d in deps}

            # Should use exact version from lock file
            assert dep_dict["Flask"].version == "2.0.3"
            assert dep_dict["Flask"].specifier == "=="

    def test_empty_directory(self):
        """Test handling of directory with no dependency files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = DependencyResolver(tmpdir)
            deps = resolver.resolve()

            assert deps == []

    def test_malformed_requirements_txt(self):
        """Test resilience to malformed requirements.txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create malformed requirements.txt
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text(
                "Flask==2.0.1\nthis is invalid line\nrequests>=2.25.0\n===broken===\n"
            )

            resolver = DependencyResolver(tmpdir)
            deps = resolver.resolve()

            # Should parse valid lines and skip invalid ones
            dep_dict = {d.name: d for d in deps}
            assert "Flask" in dep_dict
            assert "requests" in dep_dict
            assert len(dep_dict) == 2

    def test_version_specifier_parsing(self):
        """Test parsing various version specifiers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text(
                "pkg1==1.0.0\n"
                "pkg2>=2.0.0\n"
                "pkg3<=3.0.0\n"
                "pkg4~=4.0.0\n"
                "pkg5!=5.0.0,>=5.1.0\n"
                "pkg6>6.0.0,<7.0.0\n"
            )

            resolver = DependencyResolver(tmpdir)
            deps = resolver.resolve()

            dep_dict = {d.name: d for d in deps}

            assert dep_dict["pkg1"].specifier == "=="
            assert dep_dict["pkg2"].specifier == ">="
            assert dep_dict["pkg3"].specifier == "<="
            assert dep_dict["pkg4"].specifier == "~="
            # Complex specifiers: extract first operator
            assert dep_dict["pkg5"].specifier in ["!=", ">="]
            assert dep_dict["pkg6"].specifier in [">", "<"]

    def test_dependency_with_extras(self):
        """Test parsing dependencies with extras."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests[security,socks]==2.25.0\n")

            resolver = DependencyResolver(tmpdir)
            deps = resolver.resolve()

            dep_dict = {d.name: d for d in deps}
            assert "requests" in dep_dict
            assert dep_dict["requests"].version == "2.25.0"
            assert dep_dict["requests"].extras == ["security", "socks"]

    def test_git_url_dependencies(self):
        """Test handling of git URL dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text(
                "git+https://github.com/user/repo.git@v1.0.0#egg=mypackage\n"
                "Flask==2.0.1\n"
            )

            resolver = DependencyResolver(tmpdir)
            deps = resolver.resolve()

            # Should extract package name from egg parameter
            dep_dict = {d.name: d for d in deps}
            assert "Flask" in dep_dict
            # Git dependencies are tracked with source info
            if "mypackage" in dep_dict:
                assert dep_dict["mypackage"].source == "git"

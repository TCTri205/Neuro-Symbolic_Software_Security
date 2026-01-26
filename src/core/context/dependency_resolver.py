"""
Dependency Resolver for Python Projects.

Parses dependency files (requirements.txt, pyproject.toml, lock files) and
extracts package names with specific versions for Version-Aware Librarian.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Dependency:
    """Represents a resolved dependency with version information."""

    name: str
    version: Optional[str] = None
    specifier: Optional[str] = None  # ==, >=, ~=, etc.
    extras: list[str] | None = None
    source: Optional[str] = None  # pip, poetry, pipenv, git


class DependencyResolver:
    """Resolve dependencies from various Python dependency files."""

    # Priority: Lock files > requirements.txt > pyproject.toml
    LOCK_FILES = ["poetry.lock", "Pipfile.lock", "pdm.lock"]
    REQ_FILES = ["requirements.txt", "requirements-dev.txt"]
    CONFIG_FILES = ["pyproject.toml"]

    # Regex for parsing requirement lines
    # Format: package[extras]==version
    REQ_PATTERN = re.compile(
        r"^(?P<name>[a-zA-Z0-9_\-]+)"  # Package name (no dots to avoid "is invalid")
        r"(?:\[(?P<extras>[^\]]+)\])?"  # Optional extras [security,socks]
        r"\s*(?P<spec>[<>=!~]+)?\s*"  # Version specifier
        r"(?P<version>[0-9\.]+[a-zA-Z0-9\.\-]*)?$"  # Version (must end here)
    )

    # Regex for git URLs
    GIT_PATTERN = re.compile(
        r"git\+https?://[^\s]+(?:#egg=(?P<name>[a-zA-Z0-9_\-\.]+))?"
    )

    def __init__(self, project_root: str):
        """
        Initialize dependency resolver.

        Args:
            project_root: Path to the project root directory
        """
        self.project_root = Path(project_root)
        self._dependencies: dict[str, Dependency] = {}

    def resolve(self) -> list[Dependency]:
        """
        Resolve all dependencies from available files.

        Returns:
            List of resolved dependencies with version information
        """
        self._dependencies = {}

        # Priority 1: Lock files (exact versions)
        for lock_file in self.LOCK_FILES:
            if self._parse_lock_file(lock_file):
                # If lock file exists, it has priority
                # but we still parse other files for additional deps
                pass

        # Priority 2: Requirements files
        for req_file in self.REQ_FILES:
            self._parse_requirements_file(req_file)

        # Priority 3: pyproject.toml
        self._parse_pyproject()

        return list(self._dependencies.values())

    def _add_dependency(
        self,
        name: str,
        version: Optional[str] = None,
        specifier: Optional[str] = None,
        extras: list[str] | None = None,
        source: Optional[str] = None,
        force: bool = False,
    ) -> None:
        """
        Add or update a dependency.

        Args:
            name: Package name
            version: Version string
            specifier: Version specifier (==, >=, etc.)
            extras: Optional extras list
            source: Source of dependency (pip, poetry, etc.)
            force: If True, overwrite existing dependency
        """
        # Normalize name (case-insensitive for Python packages)
        normalized_name = name.lower()

        # Only add if not exists or force is True
        if normalized_name not in self._dependencies or force:
            self._dependencies[normalized_name] = Dependency(
                name=name,
                version=version,
                specifier=specifier,
                extras=extras,
                source=source,
            )

    def _parse_requirements_file(self, filename: str) -> bool:
        """
        Parse a requirements.txt style file.

        Args:
            filename: Name of requirements file

        Returns:
            True if file was parsed, False if not found
        """
        file_path = self.project_root / filename
        if not file_path.exists():
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue

                    # Remove inline comments
                    if "#" in line:
                        line = line.split("#")[0].strip()

                    # Handle git URLs
                    git_match = self.GIT_PATTERN.match(line)
                    if git_match:
                        pkg_name = git_match.group("name")
                        if pkg_name:
                            self._add_dependency(
                                name=pkg_name, source="git", specifier=None
                            )
                        continue

                    # Parse regular requirement
                    # Handle complex specifiers with commas (e.g., "pkg!=1.0,>=2.0")
                    # But don't split if comma is inside brackets (extras)
                    if "," in line and "[" not in line:
                        # Split by comma, take first spec (complex version spec)
                        first_part = line.split(",")[0].strip()
                        match = self.REQ_PATTERN.match(first_part)
                    else:
                        match = self.REQ_PATTERN.match(line)

                    if match:
                        name = match.group("name")
                        version = match.group("version")
                        specifier = match.group("spec")
                        extras_str = match.group("extras")

                        extras = None
                        if extras_str:
                            extras = [e.strip() for e in extras_str.split(",")]

                        self._add_dependency(
                            name=name,
                            version=version,
                            specifier=specifier,
                            extras=extras,
                            source="pip",
                        )
            return True
        except Exception:
            # Silently skip malformed files
            return False

    def _parse_pyproject(self) -> bool:
        """
        Parse pyproject.toml (both Poetry and PEP 621 formats).

        Returns:
            True if file was parsed, False if not found
        """
        file_path = self.project_root / "pyproject.toml"
        if not file_path.exists():
            return False

        try:
            with open(file_path, "rb") as f:
                data = tomllib.load(f)

            # Try Poetry format first
            if "tool" in data and "poetry" in data["tool"]:
                self._parse_poetry_dependencies(data["tool"]["poetry"])

            # Try PEP 621 format
            if "project" in data:
                self._parse_pep621_dependencies(data["project"])

            return True
        except Exception:
            return False

    def _parse_poetry_dependencies(self, poetry_config: dict) -> None:
        """
        Parse Poetry-style dependencies.

        Args:
            poetry_config: Poetry configuration dict
        """
        # Main dependencies
        if "dependencies" in poetry_config:
            for name, spec in poetry_config["dependencies"].items():
                if name == "python":
                    continue

                # Handle different spec formats
                if isinstance(spec, str):
                    # Simple string spec: "^2.0.0" or "2.0.1"
                    version, specifier = self._parse_version_spec(spec)
                    self._add_dependency(
                        name=name, version=version, specifier=specifier, source="poetry"
                    )
                elif isinstance(spec, dict) and "version" in spec:
                    # Dict with version key
                    version, specifier = self._parse_version_spec(spec["version"])
                    self._add_dependency(
                        name=name, version=version, specifier=specifier, source="poetry"
                    )

        # Dev dependencies
        if "dev-dependencies" in poetry_config:
            for name, spec in poetry_config["dev-dependencies"].items():
                if isinstance(spec, str):
                    version, specifier = self._parse_version_spec(spec)
                    self._add_dependency(
                        name=name, version=version, specifier=specifier, source="poetry"
                    )

    def _parse_pep621_dependencies(self, project_config: dict) -> None:
        """
        Parse PEP 621 style dependencies.

        Args:
            project_config: Project configuration dict
        """
        # Main dependencies
        if "dependencies" in project_config:
            for dep_str in project_config["dependencies"]:
                self._parse_requirement_string(dep_str, source="pep621")

        # Optional dependencies
        if "optional-dependencies" in project_config:
            for group, deps in project_config["optional-dependencies"].items():
                for dep_str in deps:
                    self._parse_requirement_string(dep_str, source="pep621")

    def _parse_requirement_string(self, req_str: str, source: str = "pip") -> None:
        """
        Parse a single requirement string.

        Args:
            req_str: Requirement string (e.g., "Flask==2.0.1")
            source: Source identifier
        """
        match = self.REQ_PATTERN.match(req_str.strip())
        if match:
            name = match.group("name")
            version = match.group("version")
            specifier = match.group("spec")
            extras_str = match.group("extras")

            extras = None
            if extras_str:
                extras = [e.strip() for e in extras_str.split(",")]

            self._add_dependency(
                name=name,
                version=version,
                specifier=specifier,
                extras=extras,
                source=source,
            )

    def _parse_version_spec(self, spec: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse a version specification string.

        Args:
            spec: Version spec (e.g., "^2.0.0", "2.0.1", ">=1.0.0")

        Returns:
            Tuple of (version, specifier)
        """
        spec = spec.strip()

        # Handle Poetry caret (^) and tilde (~) operators
        if spec.startswith("^"):
            return spec[1:], "^"
        elif spec.startswith("~"):
            return spec[1:], "~"

        # Just a version number (e.g., "2.0.1" in Poetry)
        if (
            spec
            and spec[0].isdigit()
            and not any(op in spec for op in ["<", ">", "=", "!", "~"])
        ):
            return spec, "=="

        # Handle standard pip operators (e.g., ">=2.0.0")
        # Try simple operator extraction first
        for op in ["===", "~=", "!=", "==", ">=", "<=", ">", "<"]:
            if op in spec:
                parts = spec.split(op, 1)
                if len(parts) == 2 and parts[1].strip():
                    return parts[1].strip(), op

        return None, None

    def _parse_lock_file(self, filename: str) -> bool:
        """
        Parse a lock file (poetry.lock or Pipfile.lock).

        Args:
            filename: Name of lock file

        Returns:
            True if file was parsed, False if not found
        """
        file_path = self.project_root / filename
        if not file_path.exists():
            return False

        if filename == "poetry.lock":
            return self._parse_poetry_lock(file_path)
        elif filename == "Pipfile.lock":
            return self._parse_pipfile_lock(file_path)

        return False

    def _parse_poetry_lock(self, file_path: Path) -> bool:
        """
        Parse poetry.lock file.

        Args:
            file_path: Path to poetry.lock

        Returns:
            True if successful
        """
        try:
            with open(file_path, "rb") as f:
                data = tomllib.load(f)

            if "package" in data:
                for pkg in data["package"]:
                    name = pkg.get("name")
                    version = pkg.get("version")
                    if name and version:
                        # Lock files have exact versions
                        self._add_dependency(
                            name=name,
                            version=version,
                            specifier="==",
                            source="poetry-lock",
                            force=True,  # Lock file has priority
                        )
            return True
        except Exception:
            return False

    def _parse_pipfile_lock(self, file_path: Path) -> bool:
        """
        Parse Pipfile.lock file.

        Args:
            file_path: Path to Pipfile.lock

        Returns:
            True if successful
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Parse default dependencies
            if "default" in data:
                for name, spec in data["default"].items():
                    version = spec.get("version", "").lstrip("=")
                    if version:
                        self._add_dependency(
                            name=name,
                            version=version,
                            specifier="==",
                            source="pipfile-lock",
                            force=True,
                        )

            # Parse dev dependencies
            if "develop" in data:
                for name, spec in data["develop"].items():
                    version = spec.get("version", "").lstrip("=")
                    if version:
                        self._add_dependency(
                            name=name,
                            version=version,
                            specifier="==",
                            source="pipfile-lock",
                            force=True,
                        )

            return True
        except Exception:
            return False

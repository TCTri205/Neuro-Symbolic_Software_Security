"""
Profile Registry for Librarian.

Manages library security profiles, loads from JSON files, and matches
dependencies against profiles for version-aware security analysis.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from packaging.version import parse

from src.core.context.dependency_resolver import Dependency
from src.librarian.models import FunctionSpec, Library, LibraryVersion, SecurityLabel


class ProfileRegistry:
    """
    Registry for managing library security profiles.

    Loads library profiles from JSON files and matches them against
    resolved dependencies for version-aware security analysis.
    """

    def __init__(self):
        """Initialize an empty profile registry."""
        self._libraries: dict[str, Library] = {}

    def load_from_directory(self, directory_path: str) -> None:
        """
        Load all library profiles from JSON files in a directory.

        Args:
            directory_path: Path to directory containing JSON profile files

        Note:
            - Skips invalid JSON files silently
            - Skips files that don't match Library schema
            - Only processes *.json files
        """
        dir_path = Path(directory_path)
        if not dir_path.exists():
            return

        for json_file in dir_path.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Validate against Library schema
                library = Library.model_validate(data)
                self.add_library(library)

            except (json.JSONDecodeError, ValueError, KeyError):
                # Skip invalid files silently
                continue

    def add_library(self, library: Library) -> None:
        """
        Add or update a library profile in the registry.

        Args:
            library: Library profile to add

        Note:
            If library already exists, it will be replaced.
        """
        # Normalize library name (case-insensitive)
        normalized_name = library.name.lower()
        self._libraries[normalized_name] = library

    def get_all_libraries(self) -> list[Library]:
        """
        Get all registered library profiles.

        Returns:
            List of all Library objects in the registry
        """
        return list(self._libraries.values())

    def get_profile(self, library_name: str, version: str) -> Optional[LibraryVersion]:
        """
        Get profile for a specific library and version.

        Args:
            library_name: Name of the library (case-insensitive)
            version: Exact version string to match

        Returns:
            LibraryVersion if found, None otherwise
        """
        normalized_name = library_name.lower()
        library = self._libraries.get(normalized_name)

        if not library:
            return None

        # Find exact version match
        for lib_version in library.versions:
            if lib_version.version == version:
                return lib_version

        return None

    def get_profile_latest(self, library_name: str) -> Optional[LibraryVersion]:
        """
        Get the latest version profile for a library.

        Args:
            library_name: Name of the library

        Returns:
            LibraryVersion for the latest version, None if library not found
        """
        normalized_name = library_name.lower()
        library = self._libraries.get(normalized_name)

        if not library or not library.versions:
            return None

        # Sort versions and return latest
        try:
            sorted_versions = sorted(
                library.versions,
                key=lambda v: parse(v.version),
                reverse=True,
            )
            return sorted_versions[0]
        except Exception:
            # Fallback: return last version in list
            return library.versions[-1]

    def match_dependencies(
        self, dependencies: list[Dependency]
    ) -> dict[str, LibraryVersion]:
        """
        Match resolved dependencies against library profiles.

        Args:
            dependencies: List of resolved dependencies

        Returns:
            Dictionary mapping library name to matched LibraryVersion
            Only includes dependencies that have matching profiles.

        Note:
            - If dependency has no version, uses latest available
            - Only exact version matches are returned
        """
        matches = {}

        for dep in dependencies:
            if dep.version:
                # Try exact version match
                profile = self.get_profile(dep.name, dep.version)
                if profile:
                    matches[dep.name.lower()] = profile
            else:
                # No version specified - use latest
                profile = self.get_profile_latest(dep.name)
                if profile:
                    matches[dep.name.lower()] = profile

        return matches

    def get_functions(self, library_name: str, version: str) -> list[FunctionSpec]:
        """
        Get all functions for a specific library version.

        Args:
            library_name: Name of the library
            version: Version string

        Returns:
            List of FunctionSpec objects, empty list if not found
        """
        profile = self.get_profile(library_name, version)
        if not profile:
            return []
        return profile.functions

    def get_sinks(self, library_name: str, version: str) -> list[FunctionSpec]:
        """
        Get only sink functions for a specific library version.

        Args:
            library_name: Name of the library
            version: Version string

        Returns:
            List of FunctionSpec objects with SINK label
        """
        functions = self.get_functions(library_name, version)
        return [f for f in functions if f.label == SecurityLabel.SINK]

    def get_sources(self, library_name: str, version: str) -> list[FunctionSpec]:
        """
        Get only source functions for a specific library version.

        Args:
            library_name: Name of the library
            version: Version string

        Returns:
            List of FunctionSpec objects with SOURCE label
        """
        functions = self.get_functions(library_name, version)
        return [f for f in functions if f.label == SecurityLabel.SOURCE]

    def get_sanitizers(self, library_name: str, version: str) -> list[FunctionSpec]:
        """
        Get only sanitizer functions for a specific library version.

        Args:
            library_name: Name of the library
            version: Version string

        Returns:
            List of FunctionSpec objects with SANITIZER label
        """
        functions = self.get_functions(library_name, version)
        return [f for f in functions if f.label == SecurityLabel.SANITIZER]

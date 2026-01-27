"""
Manual Model Builder for C-Extension Libraries

This module provides a fluent API for manually creating security profiles
for C-extension libraries (e.g., os, subprocess, pickle) that cannot be
analyzed through static analysis because they're compiled binary code.

Usage:
    builder = ManualModelBuilder("os", "stdlib")
    builder.add_version("3.10+")
    builder.add_sink("os.system", cwe_id="CWE-78", description="Command injection risk")
    builder.add_sink("os.popen", cwe_id="CWE-78")
    library = builder.build()
"""

from __future__ import annotations

from typing import Optional, List
from .models import (
    Library,
    LibraryVersion,
    FunctionSpec,
    SecurityLabel,
    ParameterSpec,
)


class ManualModelBuilder:
    """
    Fluent API for building Library profiles manually.

    Designed for C-extension libraries where static analysis is impossible.
    """

    def __init__(self, name: str, ecosystem: str = "pypi"):
        """
        Initialize a manual model builder.

        Args:
            name: Library name (e.g., "os", "subprocess")
            ecosystem: Package ecosystem (e.g., "pypi", "stdlib", "npm")
        """
        self.name = name
        self.ecosystem = ecosystem
        self.description: Optional[str] = None
        self.homepage: Optional[str] = None
        self.repository: Optional[str] = None
        self._versions: List[LibraryVersion] = []
        self._current_version: Optional[LibraryVersion] = None

    def set_description(self, description: str) -> ManualModelBuilder:
        """Set library description."""
        self.description = description
        return self

    def set_homepage(self, homepage: str) -> ManualModelBuilder:
        """Set library homepage URL."""
        self.homepage = homepage
        return self

    def set_repository(self, repository: str) -> ManualModelBuilder:
        """Set library repository URL."""
        self.repository = repository
        return self

    def add_version(
        self,
        version: str,
        release_date: Optional[str] = None,
        deprecated: bool = False,
    ) -> ManualModelBuilder:
        """
        Add a new version to the library profile.

        Args:
            version: Version string (e.g., "1.0.0", "3.10+")
            release_date: ISO date string (e.g., "2023-01-01")
            deprecated: Whether this version is deprecated

        Returns:
            self for method chaining
        """
        lib_version = LibraryVersion(
            version=version,
            release_date=release_date,
            deprecated=deprecated,
            functions=[],
        )
        self._versions.append(lib_version)
        self._current_version = lib_version
        return self

    def _ensure_current_version(self) -> LibraryVersion:
        """Ensure we have a current version to add functions to."""
        if self._current_version is None:
            # Auto-create a default version if none exists
            self.add_version("*")
        assert self._current_version is not None
        return self._current_version

    def add_function(
        self,
        name: str,
        label: SecurityLabel = SecurityLabel.NONE,
        parameters: Optional[List[ParameterSpec]] = None,
        returns_tainted: bool = False,
        description: Optional[str] = None,
        cwe_id: Optional[str] = None,
    ) -> ManualModelBuilder:
        """
        Add a function to the current version.

        Args:
            name: Fully qualified function name (e.g., "os.system")
            label: Security label (SOURCE, SINK, SANITIZER, NONE)
            parameters: List of parameter specifications
            returns_tainted: Whether function returns tainted data
            description: Human-readable description
            cwe_id: CWE identifier (e.g., "CWE-78")

        Returns:
            self for method chaining
        """
        version = self._ensure_current_version()
        func_spec = FunctionSpec(
            name=name,
            label=label,
            parameters=parameters or [],
            returns_tainted=returns_tainted,
            description=description,
            cwe_id=cwe_id,
        )
        version.functions.append(func_spec)
        return self

    def add_source(
        self,
        name: str,
        description: Optional[str] = None,
        returns_tainted: bool = True,
        cwe_id: Optional[str] = None,
    ) -> ManualModelBuilder:
        """
        Add a source function (produces tainted data).

        Args:
            name: Function name
            description: Description
            returns_tainted: Whether function returns tainted data (default True)
            cwe_id: CWE identifier
        """
        return self.add_function(
            name=name,
            label=SecurityLabel.SOURCE,
            returns_tainted=returns_tainted,
            description=description,
            cwe_id=cwe_id,
        )

    def add_sink(
        self,
        name: str,
        description: Optional[str] = None,
        cwe_id: Optional[str] = None,
        tainted_params: Optional[List[int]] = None,
    ) -> ManualModelBuilder:
        """
        Add a sink function (dangerous if receives tainted data).

        Args:
            name: Function name
            description: Description
            cwe_id: CWE identifier
            tainted_params: List of parameter indices that are dangerous if tainted
        """
        parameters = []
        if tainted_params:
            for idx in tainted_params:
                parameters.append(
                    ParameterSpec(
                        name=f"arg{idx}",
                        index=idx,
                        tags=["tainted"],
                    )
                )

        return self.add_function(
            name=name,
            label=SecurityLabel.SINK,
            description=description,
            cwe_id=cwe_id,
            parameters=parameters,
        )

    def add_sanitizer(
        self,
        name: str,
        description: Optional[str] = None,
    ) -> ManualModelBuilder:
        """
        Add a sanitizer function (removes taint).

        Args:
            name: Function name
            description: Description
        """
        return self.add_function(
            name=name,
            label=SecurityLabel.SANITIZER,
            description=description,
        )

    def build(self) -> Library:
        """
        Build and return the Library profile.

        Returns:
            Validated Library instance
        """
        return Library(
            name=self.name,
            ecosystem=self.ecosystem,
            versions=self._versions,
            description=self.description,
            homepage=self.homepage,
            repository=self.repository,
        )


# Pre-built profiles for common C-extension libraries
def build_os_profile() -> Library:
    """Build security profile for Python's 'os' module."""
    builder = ManualModelBuilder("os", "stdlib")
    builder.set_description("Operating system interface (C-extension)")
    builder.add_version("3.0+")

    # Command execution sinks
    builder.add_sink(
        "os.system",
        description="Execute command in shell (shell injection risk)",
        cwe_id="CWE-78",
        tainted_params=[0],
    )
    builder.add_sink(
        "os.popen",
        description="Open pipe to command (shell injection risk)",
        cwe_id="CWE-78",
        tainted_params=[0],
    )
    builder.add_sink(
        "os.execl",
        description="Execute program (command injection risk)",
        cwe_id="CWE-78",
        tainted_params=[0],
    )
    builder.add_sink(
        "os.execlp",
        description="Execute program (command injection risk)",
        cwe_id="CWE-78",
        tainted_params=[0],
    )

    # Path traversal sinks
    builder.add_sink(
        "os.remove",
        description="Delete file (path traversal risk)",
        cwe_id="CWE-22",
        tainted_params=[0],
    )
    builder.add_sink(
        "os.unlink",
        description="Delete file (path traversal risk)",
        cwe_id="CWE-22",
        tainted_params=[0],
    )

    # Environment sources
    builder.add_source(
        "os.getenv",
        description="Get environment variable (untrusted input)",
        cwe_id="CWE-15",
    )
    builder.add_source(
        "os.environ.get",
        description="Get environment variable (untrusted input)",
        cwe_id="CWE-15",
    )

    return builder.build()


def build_subprocess_profile() -> Library:
    """Build security profile for Python's 'subprocess' module."""
    builder = ManualModelBuilder("subprocess", "stdlib")
    builder.set_description("Subprocess management (C-extension)")
    builder.add_version("3.0+")

    # Command execution sinks
    builder.add_sink(
        "subprocess.call",
        description="Execute command (shell injection if shell=True)",
        cwe_id="CWE-78",
        tainted_params=[0],
    )
    builder.add_sink(
        "subprocess.check_call",
        description="Execute command (shell injection if shell=True)",
        cwe_id="CWE-78",
        tainted_params=[0],
    )
    builder.add_sink(
        "subprocess.check_output",
        description="Execute command (shell injection if shell=True)",
        cwe_id="CWE-78",
        tainted_params=[0],
    )
    builder.add_sink(
        "subprocess.run",
        description="Execute command (shell injection if shell=True)",
        cwe_id="CWE-78",
        tainted_params=[0],
    )
    builder.add_sink(
        "subprocess.Popen",
        description="Execute command (shell injection if shell=True)",
        cwe_id="CWE-78",
        tainted_params=[0],
    )

    return builder.build()


def build_pickle_profile() -> Library:
    """Build security profile for Python's 'pickle' module."""
    builder = ManualModelBuilder("pickle", "stdlib")
    builder.set_description("Python object serialization (C-extension)")
    builder.add_version("3.0+")

    # Deserialization sinks
    builder.add_sink(
        "pickle.loads",
        description="Deserialize object (arbitrary code execution risk)",
        cwe_id="CWE-502",
        tainted_params=[0],
    )
    builder.add_sink(
        "pickle.load",
        description="Deserialize object from file (arbitrary code execution risk)",
        cwe_id="CWE-502",
        tainted_params=[0],
    )

    return builder.build()


# Export pre-built profiles
STDLIB_PROFILES = {
    "os": build_os_profile,
    "subprocess": build_subprocess_profile,
    "pickle": build_pickle_profile,
}


def get_stdlib_profile(name: str) -> Optional[Library]:
    """
    Get a pre-built stdlib profile by name.

    Args:
        name: Module name (e.g., "os", "subprocess")

    Returns:
        Library profile or None if not found
    """
    builder_fn = STDLIB_PROFILES.get(name.lower())
    if builder_fn:
        return builder_fn()
    return None

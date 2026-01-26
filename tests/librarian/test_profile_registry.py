"""
Tests for ProfileRegistry.

Tests loading and matching library profiles against resolved dependencies.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.core.context.dependency_resolver import Dependency
from src.librarian.models import (
    FunctionSpec,
    Library,
    LibraryVersion,
    ParameterSpec,
    SecurityLabel,
)
from src.librarian.registry import ProfileRegistry


# --- Fixtures ---


@pytest.fixture
def temp_profile_dir():
    """Create temporary directory for profile JSON files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_requests_profile():
    """Create a sample requests library profile."""
    return Library(
        name="requests",
        ecosystem="pypi",
        description="HTTP library for Python",
        homepage="https://requests.readthedocs.io",
        versions=[
            LibraryVersion(
                version="2.28.0",
                functions=[
                    FunctionSpec(
                        name="requests.get",
                        label=SecurityLabel.SINK,
                        description="HTTP GET request - potential SSRF",
                        cwe_id="CWE-918",
                        parameters=[
                            ParameterSpec(
                                name="url",
                                index=0,
                                tags=["network", "url"],
                                description="Target URL",
                            )
                        ],
                    ),
                    FunctionSpec(
                        name="requests.post",
                        label=SecurityLabel.SINK,
                        description="HTTP POST request",
                        cwe_id="CWE-918",
                    ),
                ],
            ),
            LibraryVersion(
                version="2.31.0",
                functions=[
                    FunctionSpec(
                        name="requests.get",
                        label=SecurityLabel.SINK,
                        description="HTTP GET request - SSRF mitigation improved",
                        cwe_id="CWE-918",
                    )
                ],
            ),
        ],
    )


@pytest.fixture
def sample_flask_profile():
    """Create a sample Flask library profile."""
    return Library(
        name="flask",
        ecosystem="pypi",
        description="Web framework",
        versions=[
            LibraryVersion(
                version="2.0.0",
                functions=[
                    FunctionSpec(
                        name="flask.render_template_string",
                        label=SecurityLabel.SINK,
                        description="Template injection vulnerability",
                        cwe_id="CWE-94",
                    )
                ],
            )
        ],
    )


# --- Tests: Registry Loading ---


def test_registry_creation_empty():
    """Test creating an empty profile registry."""
    registry = ProfileRegistry()
    assert len(registry.get_all_libraries()) == 0


def test_load_from_json_single_file(temp_profile_dir, sample_requests_profile):
    """Test loading a single profile JSON file."""
    profile_file = temp_profile_dir / "requests.json"
    profile_file.write_text(sample_requests_profile.model_dump_json(indent=2))

    registry = ProfileRegistry()
    registry.load_from_directory(str(temp_profile_dir))

    libraries = registry.get_all_libraries()
    assert len(libraries) == 1
    assert libraries[0].name == "requests"
    assert len(libraries[0].versions) == 2


def test_load_from_json_multiple_files(
    temp_profile_dir, sample_requests_profile, sample_flask_profile
):
    """Test loading multiple profile files."""
    (temp_profile_dir / "requests.json").write_text(
        sample_requests_profile.model_dump_json()
    )
    (temp_profile_dir / "flask.json").write_text(sample_flask_profile.model_dump_json())

    registry = ProfileRegistry()
    registry.load_from_directory(str(temp_profile_dir))

    libraries = registry.get_all_libraries()
    assert len(libraries) == 2
    names = {lib.name for lib in libraries}
    assert names == {"requests", "flask"}


def test_load_from_json_invalid_file(temp_profile_dir):
    """Test loading invalid JSON file (should skip gracefully)."""
    invalid_file = temp_profile_dir / "invalid.json"
    invalid_file.write_text("{invalid json")

    registry = ProfileRegistry()
    registry.load_from_directory(str(temp_profile_dir))

    # Should skip invalid file without crashing
    assert len(registry.get_all_libraries()) == 0


def test_load_from_json_non_library_schema(temp_profile_dir):
    """Test loading JSON that doesn't match Library schema."""
    bad_file = temp_profile_dir / "bad.json"
    bad_file.write_text(json.dumps({"foo": "bar"}))

    registry = ProfileRegistry()
    registry.load_from_directory(str(temp_profile_dir))

    # Should skip invalid schema
    assert len(registry.get_all_libraries()) == 0


def test_load_from_directory_no_json_files(temp_profile_dir):
    """Test loading from directory with no JSON files."""
    (temp_profile_dir / "readme.txt").write_text("No JSON here")

    registry = ProfileRegistry()
    registry.load_from_directory(str(temp_profile_dir))

    assert len(registry.get_all_libraries()) == 0


# --- Tests: Profile Matching ---


def test_get_profile_exact_version(sample_requests_profile):
    """Test retrieving profile for exact version match."""
    registry = ProfileRegistry()
    registry.add_library(sample_requests_profile)

    profile = registry.get_profile("requests", "2.28.0")
    assert profile is not None
    assert profile.version == "2.28.0"
    assert len(profile.functions) == 2


def test_get_profile_version_not_found(sample_requests_profile):
    """Test retrieving profile for non-existent version."""
    registry = ProfileRegistry()
    registry.add_library(sample_requests_profile)

    profile = registry.get_profile("requests", "999.0.0")
    assert profile is None


def test_get_profile_library_not_found():
    """Test retrieving profile for non-existent library."""
    registry = ProfileRegistry()

    profile = registry.get_profile("nonexistent", "1.0.0")
    assert profile is None


def test_get_profile_latest_version(sample_requests_profile):
    """Test retrieving latest version when multiple versions exist."""
    registry = ProfileRegistry()
    registry.add_library(sample_requests_profile)

    profile = registry.get_profile_latest("requests")
    assert profile is not None
    assert profile.version == "2.31.0"  # Latest version


def test_get_profile_latest_library_not_found():
    """Test retrieving latest profile for non-existent library."""
    registry = ProfileRegistry()

    profile = registry.get_profile_latest("nonexistent")
    assert profile is None


# --- Tests: Dependency Matching ---


def test_match_dependencies_exact_match(sample_requests_profile, sample_flask_profile):
    """Test matching dependencies with exact versions."""
    registry = ProfileRegistry()
    registry.add_library(sample_requests_profile)
    registry.add_library(sample_flask_profile)

    dependencies = [
        Dependency(name="requests", version="2.28.0", specifier="=="),
        Dependency(name="flask", version="2.0.0", specifier="=="),
    ]

    matches = registry.match_dependencies(dependencies)
    assert len(matches) == 2
    assert "requests" in matches
    assert "flask" in matches
    assert matches["requests"].version == "2.28.0"
    assert matches["flask"].version == "2.0.0"


def test_match_dependencies_partial_match(sample_requests_profile):
    """Test matching when only some dependencies have profiles."""
    registry = ProfileRegistry()
    registry.add_library(sample_requests_profile)

    dependencies = [
        Dependency(name="requests", version="2.28.0", specifier="=="),
        Dependency(name="unknown-lib", version="1.0.0", specifier="=="),
    ]

    matches = registry.match_dependencies(dependencies)
    assert len(matches) == 1
    assert "requests" in matches
    assert "unknown-lib" not in matches


def test_match_dependencies_no_version_specified(sample_requests_profile):
    """Test matching dependency without version (should use latest)."""
    registry = ProfileRegistry()
    registry.add_library(sample_requests_profile)

    dependencies = [
        Dependency(name="requests", version=None, specifier=None),
    ]

    matches = registry.match_dependencies(dependencies)
    assert len(matches) == 1
    assert matches["requests"].version == "2.31.0"  # Latest


def test_match_dependencies_empty_list():
    """Test matching empty dependency list."""
    registry = ProfileRegistry()
    matches = registry.match_dependencies([])
    assert len(matches) == 0


# --- Tests: Profile Addition ---


def test_add_library_new(sample_requests_profile):
    """Test adding a new library to the registry."""
    registry = ProfileRegistry()
    registry.add_library(sample_requests_profile)

    libraries = registry.get_all_libraries()
    assert len(libraries) == 1
    assert libraries[0].name == "requests"


def test_add_library_duplicate_replaces(sample_requests_profile):
    """Test adding duplicate library replaces existing."""
    registry = ProfileRegistry()
    registry.add_library(sample_requests_profile)

    # Add modified version
    modified = sample_requests_profile.model_copy(deep=True)
    modified.description = "Modified description"
    registry.add_library(modified)

    libraries = registry.get_all_libraries()
    assert len(libraries) == 1
    assert libraries[0].description == "Modified description"


# --- Tests: Function Retrieval ---


def test_get_functions_for_library(sample_requests_profile):
    """Test retrieving all functions for a specific library version."""
    registry = ProfileRegistry()
    registry.add_library(sample_requests_profile)

    functions = registry.get_functions("requests", "2.28.0")
    assert len(functions) == 2
    assert {func.name for func in functions} == {"requests.get", "requests.post"}


def test_get_functions_library_not_found():
    """Test retrieving functions for non-existent library."""
    registry = ProfileRegistry()
    functions = registry.get_functions("nonexistent", "1.0.0")
    assert len(functions) == 0


def test_get_sinks_only(sample_requests_profile):
    """Test retrieving only sink functions."""
    registry = ProfileRegistry()
    registry.add_library(sample_requests_profile)

    sinks = registry.get_sinks("requests", "2.28.0")
    assert len(sinks) == 2
    assert all(func.label == SecurityLabel.SINK for func in sinks)


def test_get_sources_only():
    """Test retrieving only source functions."""
    # Create profile with source
    lib = Library(
        name="testlib",
        ecosystem="pypi",
        versions=[
            LibraryVersion(
                version="1.0.0",
                functions=[
                    FunctionSpec(
                        name="testlib.get_user_input",
                        label=SecurityLabel.SOURCE,
                    ),
                    FunctionSpec(
                        name="testlib.execute_command",
                        label=SecurityLabel.SINK,
                    ),
                ],
            )
        ],
    )

    registry = ProfileRegistry()
    registry.add_library(lib)

    sources = registry.get_sources("testlib", "1.0.0")
    assert len(sources) == 1
    assert sources[0].label == SecurityLabel.SOURCE


def test_get_sanitizers_only():
    """Test retrieving only sanitizer functions."""
    lib = Library(
        name="testlib",
        ecosystem="pypi",
        versions=[
            LibraryVersion(
                version="1.0.0",
                functions=[
                    FunctionSpec(
                        name="testlib.sanitize_sql",
                        label=SecurityLabel.SANITIZER,
                    ),
                    FunctionSpec(
                        name="testlib.execute_query",
                        label=SecurityLabel.SINK,
                    ),
                ],
            )
        ],
    )

    registry = ProfileRegistry()
    registry.add_library(lib)

    sanitizers = registry.get_sanitizers("testlib", "1.0.0")
    assert len(sanitizers) == 1
    assert sanitizers[0].label == SecurityLabel.SANITIZER

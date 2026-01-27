"""
Tests for Manual Model Builder

Test the fluent API for creating security profiles for C-extension libraries.
"""

from src.librarian.manual_models import (
    ManualModelBuilder,
    build_os_profile,
    build_subprocess_profile,
    build_pickle_profile,
    get_stdlib_profile,
)
from src.librarian.models import SecurityLabel, Library


class TestManualModelBuilder:
    """Test ManualModelBuilder fluent API."""

    def test_basic_builder_creation(self):
        """Test creating a basic library profile."""
        builder = ManualModelBuilder("test_lib", "pypi")
        library = builder.build()

        assert library.name == "test_lib"
        assert library.ecosystem == "pypi"
        assert len(library.versions) == 0

    def test_builder_with_metadata(self):
        """Test setting library metadata."""
        builder = ManualModelBuilder("test_lib", "pypi")
        builder.set_description("Test library")
        builder.set_homepage("https://test.com")
        builder.set_repository("https://github.com/test/test")

        library = builder.build()

        assert library.description == "Test library"
        assert library.homepage == "https://test.com"
        assert library.repository == "https://github.com/test/test"

    def test_fluent_chaining(self):
        """Test method chaining works correctly."""
        library = (
            ManualModelBuilder("test_lib", "pypi")
            .set_description("Test")
            .set_homepage("https://test.com")
            .add_version("1.0.0")
            .build()
        )

        assert library.name == "test_lib"
        assert library.description == "Test"
        assert len(library.versions) == 1

    def test_add_version(self):
        """Test adding versions."""
        builder = ManualModelBuilder("test_lib", "pypi")
        builder.add_version("1.0.0", release_date="2023-01-01", deprecated=False)
        builder.add_version("2.0.0", release_date="2024-01-01", deprecated=False)

        library = builder.build()

        assert len(library.versions) == 2
        assert library.versions[0].version == "1.0.0"
        assert library.versions[0].release_date == "2023-01-01"
        assert library.versions[1].version == "2.0.0"

    def test_add_function_basic(self):
        """Test adding a basic function."""
        builder = ManualModelBuilder("test_lib", "pypi")
        builder.add_version("1.0.0")
        builder.add_function("test.func", label=SecurityLabel.NONE)

        library = builder.build()

        assert len(library.versions[0].functions) == 1
        func = library.versions[0].functions[0]
        assert func.name == "test.func"
        assert func.label == SecurityLabel.NONE

    def test_add_source(self):
        """Test adding a source function."""
        builder = ManualModelBuilder("test_lib", "pypi")
        builder.add_version("1.0.0")
        builder.add_source(
            "test.get_input",
            description="Gets user input",
            cwe_id="CWE-20",
        )

        library = builder.build()
        func = library.versions[0].functions[0]

        assert func.name == "test.get_input"
        assert func.label == SecurityLabel.SOURCE
        assert func.returns_tainted is True
        assert func.description == "Gets user input"
        assert func.cwe_id == "CWE-20"

    def test_add_sink(self):
        """Test adding a sink function."""
        builder = ManualModelBuilder("test_lib", "pypi")
        builder.add_version("1.0.0")
        builder.add_sink(
            "test.execute",
            description="Executes command",
            cwe_id="CWE-78",
            tainted_params=[0, 1],
        )

        library = builder.build()
        func = library.versions[0].functions[0]

        assert func.name == "test.execute"
        assert func.label == SecurityLabel.SINK
        assert func.description == "Executes command"
        assert func.cwe_id == "CWE-78"
        assert len(func.parameters) == 2
        assert func.parameters[0].index == 0
        assert func.parameters[0].tags == ["tainted"]
        assert func.parameters[1].index == 1

    def test_add_sanitizer(self):
        """Test adding a sanitizer function."""
        builder = ManualModelBuilder("test_lib", "pypi")
        builder.add_version("1.0.0")
        builder.add_sanitizer(
            "test.escape_html",
            description="Escapes HTML characters",
        )

        library = builder.build()
        func = library.versions[0].functions[0]

        assert func.name == "test.escape_html"
        assert func.label == SecurityLabel.SANITIZER
        assert func.description == "Escapes HTML characters"

    def test_auto_version_creation(self):
        """Test that adding functions without version auto-creates '*' version."""
        builder = ManualModelBuilder("test_lib", "pypi")
        # Don't add version explicitly
        builder.add_sink("test.func")

        library = builder.build()

        assert len(library.versions) == 1
        assert library.versions[0].version == "*"
        assert len(library.versions[0].functions) == 1

    def test_multiple_functions_same_version(self):
        """Test adding multiple functions to same version."""
        builder = ManualModelBuilder("test_lib", "pypi")
        builder.add_version("1.0.0")
        builder.add_source("test.source")
        builder.add_sink("test.sink")
        builder.add_sanitizer("test.sanitizer")

        library = builder.build()

        assert len(library.versions) == 1
        assert len(library.versions[0].functions) == 3

        labels = {f.label for f in library.versions[0].functions}
        assert labels == {
            SecurityLabel.SOURCE,
            SecurityLabel.SINK,
            SecurityLabel.SANITIZER,
        }

    def test_functions_across_versions(self):
        """Test adding functions to multiple versions."""
        builder = ManualModelBuilder("test_lib", "pypi")

        # Version 1.0.0 has one function
        builder.add_version("1.0.0")
        builder.add_sink("test.old_func")

        # Version 2.0.0 has two functions
        builder.add_version("2.0.0")
        builder.add_sink("test.old_func")
        builder.add_sink("test.new_func")

        library = builder.build()

        assert len(library.versions) == 2
        assert len(library.versions[0].functions) == 1
        assert len(library.versions[1].functions) == 2

    def test_deprecated_version(self):
        """Test marking a version as deprecated."""
        builder = ManualModelBuilder("test_lib", "pypi")
        builder.add_version("1.0.0", deprecated=True)

        library = builder.build()

        assert library.versions[0].deprecated is True


class TestPrebuiltProfiles:
    """Test pre-built stdlib profiles."""

    def test_build_os_profile(self):
        """Test os module profile."""
        library = build_os_profile()

        assert library.name == "os"
        assert library.ecosystem == "stdlib"
        assert len(library.versions) == 1
        assert library.versions[0].version == "3.0+"

        # Check for key dangerous functions
        func_names = {f.name for f in library.versions[0].functions}
        assert "os.system" in func_names
        assert "os.popen" in func_names
        assert "os.getenv" in func_names

        # Verify labels
        sinks = [
            f for f in library.versions[0].functions if f.label == SecurityLabel.SINK
        ]
        sources = [
            f for f in library.versions[0].functions if f.label == SecurityLabel.SOURCE
        ]

        assert len(sinks) > 0
        assert len(sources) > 0

        # Verify CWE tags
        system_func = next(
            f for f in library.versions[0].functions if f.name == "os.system"
        )
        assert system_func.cwe_id == "CWE-78"

    def test_build_subprocess_profile(self):
        """Test subprocess module profile."""
        library = build_subprocess_profile()

        assert library.name == "subprocess"
        assert library.ecosystem == "stdlib"

        func_names = {f.name for f in library.versions[0].functions}
        assert "subprocess.call" in func_names
        assert "subprocess.run" in func_names
        assert "subprocess.Popen" in func_names

        # All subprocess functions should be sinks
        for func in library.versions[0].functions:
            assert func.label == SecurityLabel.SINK
            assert func.cwe_id == "CWE-78"

    def test_build_pickle_profile(self):
        """Test pickle module profile."""
        library = build_pickle_profile()

        assert library.name == "pickle"
        assert library.ecosystem == "stdlib"

        func_names = {f.name for f in library.versions[0].functions}
        assert "pickle.loads" in func_names
        assert "pickle.load" in func_names

        # All pickle functions should be sinks with CWE-502
        for func in library.versions[0].functions:
            assert func.label == SecurityLabel.SINK
            assert func.cwe_id == "CWE-502"

    def test_get_stdlib_profile_os(self):
        """Test retrieving os profile by name."""
        library = get_stdlib_profile("os")

        assert library is not None
        assert library.name == "os"

    def test_get_stdlib_profile_case_insensitive(self):
        """Test case-insensitive profile lookup."""
        library = get_stdlib_profile("OS")

        assert library is not None
        assert library.name == "os"

    def test_get_stdlib_profile_not_found(self):
        """Test retrieving non-existent profile."""
        library = get_stdlib_profile("nonexistent")

        assert library is None

    def test_all_stdlib_profiles_valid(self):
        """Test that all pre-built profiles are valid Pydantic models."""
        profiles = ["os", "subprocess", "pickle"]

        for profile_name in profiles:
            library = get_stdlib_profile(profile_name)
            assert library is not None
            assert isinstance(library, Library)

            # Validate structure
            assert library.name
            assert library.ecosystem == "stdlib"
            assert len(library.versions) > 0

            # Validate all functions
            for version in library.versions:
                for func in version.functions:
                    assert func.name
                    assert func.label in SecurityLabel


class TestProfileIntegration:
    """Test integration with ProfileRegistry."""

    def test_manual_profile_compatible_with_registry(self):
        """Test that manually built profiles work with ProfileRegistry."""
        from src.librarian.registry import ProfileRegistry

        # Build a custom profile
        builder = ManualModelBuilder("test_lib", "pypi")
        builder.add_version("1.0.0")
        builder.add_sink("test.dangerous_func", cwe_id="CWE-78")
        library = builder.build()

        # Add to registry
        registry = ProfileRegistry()
        registry.add_library(library)

        # Retrieve it (get_profile returns LibraryVersion, not Library)
        profile = registry.get_profile("test_lib", "1.0.0")
        assert profile is not None
        assert profile.version == "1.0.0"
        assert len(profile.functions) == 1

    def test_stdlib_profiles_in_registry(self):
        """Test loading stdlib profiles into registry."""
        from src.librarian.registry import ProfileRegistry

        registry = ProfileRegistry()

        # Add all stdlib profiles
        for profile_name in ["os", "subprocess", "pickle"]:
            library = get_stdlib_profile(profile_name)
            assert library is not None
            registry.add_library(library)

        # Verify retrieval (get_profile returns LibraryVersion)
        os_profile = registry.get_profile("os", "3.0+")
        assert os_profile is not None
        assert len(os_profile.functions) > 0

    def test_get_sinks_from_manual_profile(self):
        """Test filtering sinks from manual profile via registry."""
        from src.librarian.registry import ProfileRegistry

        builder = ManualModelBuilder("test_lib", "pypi")
        builder.add_version("1.0.0")
        builder.add_sink("test.sink1")
        builder.add_sink("test.sink2")
        builder.add_source("test.source1")
        library = builder.build()

        registry = ProfileRegistry()
        registry.add_library(library)

        sinks = registry.get_sinks("test_lib", "1.0.0")
        assert len(sinks) == 2
        assert {s.name for s in sinks} == {"test.sink1", "test.sink2"}


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_library(self):
        """Test building library with no versions or functions."""
        builder = ManualModelBuilder("empty_lib", "pypi")
        library = builder.build()

        assert library.name == "empty_lib"
        assert len(library.versions) == 0

    def test_version_with_no_functions(self):
        """Test version with no functions."""
        builder = ManualModelBuilder("test_lib", "pypi")
        builder.add_version("1.0.0")

        library = builder.build()

        assert len(library.versions) == 1
        assert len(library.versions[0].functions) == 0

    def test_sink_with_no_tainted_params(self):
        """Test sink without specifying tainted parameters."""
        builder = ManualModelBuilder("test_lib", "pypi")
        builder.add_version("1.0.0")
        builder.add_sink("test.func")

        library = builder.build()
        func = library.versions[0].functions[0]

        assert func.label == SecurityLabel.SINK
        assert len(func.parameters) == 0

    def test_multiple_builders_independent(self):
        """Test that multiple builders don't interfere with each other."""
        builder1 = ManualModelBuilder("lib1", "pypi")
        builder1.add_version("1.0.0")
        builder1.add_sink("lib1.func")

        builder2 = ManualModelBuilder("lib2", "pypi")
        builder2.add_version("2.0.0")
        builder2.add_source("lib2.func")

        lib1 = builder1.build()
        lib2 = builder2.build()

        assert lib1.name == "lib1"
        assert lib2.name == "lib2"
        assert len(lib1.versions[0].functions) == 1
        assert len(lib2.versions[0].functions) == 1
        assert lib1.versions[0].functions[0].label == SecurityLabel.SINK
        assert lib2.versions[0].functions[0].label == SecurityLabel.SOURCE

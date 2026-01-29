"""
Unit tests for Joern integration stub.
These tests verify that the JoernStub interface works correctly
and returns IR-compatible data structures.
"""

import logging
from unittest.mock import patch
import pytest
from src.core.interop.joern import ExternalParser, JoernStub


def test_external_parser_is_abstract():
    """Test that ExternalParser is an abstract base class."""
    with pytest.raises(TypeError):
        # Should not be able to instantiate abstract class
        ExternalParser()  # type: ignore


def test_joern_stub_instantiation():
    """Test that JoernStub can be instantiated."""
    stub = JoernStub()
    assert stub is not None
    assert isinstance(stub, ExternalParser)


def test_joern_stub_check_installed_returns_false():
    """Test that check_installed returns False (not yet implemented)."""
    stub = JoernStub()
    result = stub.check_installed()
    assert result is False


def test_joern_stub_parse_file_returns_empty_ir():
    """Test that parse_file returns a valid empty IR structure."""
    stub = JoernStub()
    result = stub.parse_file("dummy_file.c")

    # Verify structure matches IR schema
    assert isinstance(result, dict)
    assert "nodes" in result
    assert "edges" in result
    assert "metadata" in result

    # Verify empty state
    assert result["nodes"] == []
    assert result["edges"] == []

    # Verify metadata
    assert result["metadata"]["parser"] == "joern-stub"


def test_joern_stub_parse_file_logs_warning(caplog):
    """Test that parse_file logs a warning about not being implemented."""
    stub = JoernStub()

    with caplog.at_level(logging.WARNING):
        stub.parse_file("test.java")

    # Check that a warning was logged
    assert len(caplog.records) > 0
    assert any(
        "Joern integration is not yet implemented" in record.message
        for record in caplog.records
    )


def test_joern_stub_parse_file_handles_various_paths():
    """Test that parse_file works with different file paths."""
    stub = JoernStub()

    test_paths = [
        "test.c",
        "path/to/file.cpp",
        "/absolute/path/file.java",
        "file_with_underscore.c",
        "file-with-dash.cpp",
    ]

    for path in test_paths:
        result = stub.parse_file(path)
        assert isinstance(result, dict)
        assert "nodes" in result
        assert "edges" in result


def test_joern_stub_parse_file_structure_matches_ir_schema():
    """Test that the returned structure strictly matches NSSS IR schema."""
    stub = JoernStub()
    result = stub.parse_file("example.c")

    # Verify top-level keys only
    expected_keys = {"nodes", "edges", "metadata"}
    assert set(result.keys()) == expected_keys

    # Verify types
    assert isinstance(result["nodes"], list)
    assert isinstance(result["edges"], list)
    assert isinstance(result["metadata"], dict)


def test_joern_stub_check_installed_with_subprocess_mock():
    """Test check_installed behavior when subprocess is available."""
    stub = JoernStub()

    # Currently returns False; in future implementation, this would check subprocess
    with patch("subprocess.run") as mock_run:
        # Even with subprocess available, current stub returns False
        result = stub.check_installed()
        assert result is False
        # Verify subprocess was NOT called (not implemented yet)
        assert mock_run.call_count == 0


def test_joern_stub_is_subclass_of_external_parser():
    """Test that JoernStub properly inherits from ExternalParser."""
    assert issubclass(JoernStub, ExternalParser)

    stub = JoernStub()
    assert hasattr(stub, "parse_file")
    assert hasattr(stub, "check_installed")
    assert callable(stub.parse_file)
    assert callable(stub.check_installed)


def test_joern_stub_parse_file_is_deterministic():
    """Test that calling parse_file multiple times with same input gives same result."""
    stub = JoernStub()
    file_path = "test.c"

    result1 = stub.parse_file(file_path)
    result2 = stub.parse_file(file_path)

    # Results should be identical
    assert result1 == result2
    assert result1["nodes"] == result2["nodes"]
    assert result1["edges"] == result2["edges"]
    assert result1["metadata"] == result2["metadata"]

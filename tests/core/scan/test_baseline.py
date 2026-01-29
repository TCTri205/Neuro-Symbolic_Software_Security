import os
import pytest
import tempfile
from typing import List, Dict, Any
from src.core.scan.baseline import BaselineEngine


@pytest.fixture
def temp_baseline_file():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def mock_findings() -> List[Dict[str, Any]]:
    return [
        {
            "rule_id": "TEST-001",
            "file": "src/app.py",
            "line": 3,
            "column": 5,
            "sink": "exec",
            "source": "input",
            "end_line": 3,
        },
        {
            "rule_id": "TEST-002",
            "file": "src/db.py",
            "line": 20,
            "column": 1,
            "message": "SQL Injection",
            # Missing sink/source to test extraction defaults
        },
    ]


@pytest.fixture
def mock_source_lines() -> List[str]:
    return ["import os", "def foo():", "    exec(input())", "    pass"]


def test_baseline_empty_load(temp_baseline_file):
    """Test loading from a non-existent or empty file."""
    # Case 1: Non-existent file
    if os.path.exists(temp_baseline_file):
        os.remove(temp_baseline_file)

    engine = BaselineEngine(storage_path=temp_baseline_file)
    data = engine.load()
    assert len(data.entries) == 0
    assert engine.summary()["total"] == 0

    # Case 2: Empty file
    with open(temp_baseline_file, "w") as f:
        f.write("")

    engine = BaselineEngine(storage_path=temp_baseline_file)
    data = engine.load()
    assert len(data.entries) == 0

    # Case 3: Invalid JSON
    with open(temp_baseline_file, "w") as f:
        f.write("{invalid json")

    engine = BaselineEngine(storage_path=temp_baseline_file)
    data = engine.load()
    assert len(data.entries) == 0


def test_baseline_save_and_load(temp_baseline_file, mock_findings, mock_source_lines):
    """Test saving findings to baseline and reloading them."""
    engine = BaselineEngine(storage_path=temp_baseline_file)

    entries = engine.build_entries(mock_findings, "src/app.py", mock_source_lines)
    # mock_findings has 2 items, both should produce entries
    assert len(entries) == 2

    engine.save(entries)

    # Reload
    new_engine = BaselineEngine(storage_path=temp_baseline_file)
    assert len(new_engine._entries) == 2

    # Check content of first entry
    entry = new_engine._entries[entries[0].fingerprint]
    assert entry.rule_id == "TEST-001"
    assert entry.file == "src/app.py"


def test_fingerprint_stability(temp_baseline_file, mock_findings, mock_source_lines):
    """Test that fingerprint remains stable across whitespace changes."""
    engine = BaselineEngine(storage_path=temp_baseline_file)

    # Original code
    code_a = ["def main():", "    x = 1", "    eval(x)"]
    finding = mock_findings[0]

    f1 = engine.fingerprint_for_finding(finding, "src/app.py", code_a)

    # Modified whitespace
    code_b = ["def main():", "    x = 1  ", "    eval(x)   "]
    f2 = engine.fingerprint_for_finding(finding, "src/app.py", code_b)

    assert f1 == f2
    assert "TEST-001" in f1


def test_fingerprint_sensitivity(temp_baseline_file, mock_findings):
    """Test that fingerprint changes when logic changes."""
    engine = BaselineEngine(storage_path=temp_baseline_file)
    finding = mock_findings[0]

    # Finding points to line 3. We must provide enough lines.
    code_a = ["# line 1", "# line 2", "eval(x)"]
    code_b = ["# line 1", "# line 2", "eval(y)"]  # Logic change

    f1 = engine.fingerprint_for_finding(finding, "src/app.py", code_a)
    f2 = engine.fingerprint_for_finding(finding, "src/app.py", code_b)

    assert f1 != f2


def test_filter_findings(temp_baseline_file, mock_findings, mock_source_lines):
    """Test filtering new vs existing findings."""
    engine = BaselineEngine(storage_path=temp_baseline_file)

    # Add first finding to baseline
    entries = engine.build_entries([mock_findings[0]], "src/app.py", mock_source_lines)
    engine.save(entries)

    # Reload and filter
    reloaded = BaselineEngine(storage_path=temp_baseline_file)

    # Pass both findings: one should be existing, one new
    new_findings, stats = reloaded.filter_findings(
        mock_findings, "src/app.py", mock_source_lines
    )

    assert len(new_findings) == 1
    assert new_findings[0]["rule_id"] == "TEST-002"
    assert stats["new"] == 1
    assert stats["existing"] == 1

    # Summary check
    summary = reloaded.summary()
    assert summary["total"] == 1
    assert summary["existing"] == 1
    assert summary["new"] == 1


def test_path_normalization(temp_baseline_file):
    """Test file path normalization logic."""
    project_root = os.path.abspath("/tmp/project")
    engine = BaselineEngine(storage_path=temp_baseline_file, project_root=project_root)

    # Relative path should stay relative
    assert engine._normalize_file_path("src/app.py") == "src/app.py"

    # Absolute path inside project should become relative
    abs_path = os.path.join(project_root, "src/app.py")
    assert engine._normalize_file_path(abs_path) == "src/app.py"

    # Windows separators should be normalized
    assert engine._normalize_file_path("src\\app.py") == "src/app.py"

    # Absolute path outside project (edge case, might stay absolute or fail relpath)
    # We mock os.path.relpath to ensure deterministic behavior for test if needed,
    # but let's trust standard behavior for now.


def test_snippet_extraction_edge_cases(temp_baseline_file):
    """Test snippet extraction with out-of-bounds lines."""
    engine = BaselineEngine(storage_path=temp_baseline_file)
    lines = ["line1", "line2", "line3"]

    # Valid range
    assert engine._extract_snippet_lines(lines, 1, 2) == ["line1", "line2"]

    # Start line too high
    assert engine._extract_snippet_lines(lines, 10, 12) == []

    # End line too high (should cap)
    assert engine._extract_snippet_lines(lines, 2, 10) == ["line2", "line3"]

    # Empty lines
    assert engine._extract_snippet_lines([], 1, 2) == []


def test_extract_integers_defaults(temp_baseline_file):
    """Test integer extraction with bad data."""
    engine = BaselineEngine(storage_path=temp_baseline_file)

    assert engine._extract_int({"line": "abc"}, "line") == 1
    assert engine._extract_int({"line": "10"}, "line") == 10
    assert engine._extract_int({"line": 5}, "line") == 5

    assert engine._extract_end_line({"end_line": "bad"}, 5) == 5

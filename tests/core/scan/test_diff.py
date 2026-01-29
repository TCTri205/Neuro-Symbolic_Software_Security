import os
import pytest
from unittest.mock import MagicMock, patch
from src.core.scan.diff import DiffScanner
from src.core.parser.ir import IRGraph, IRNode


@pytest.fixture
def diff_scanner(tmp_path):
    # Create a dummy project structure
    d = tmp_path / "src"
    d.mkdir()
    (d / "app.py").touch()
    (d / "utils.py").touch()
    (d / "core.py").touch()

    return DiffScanner(str(tmp_path))


@patch("subprocess.run")
def test_get_changed_files(mock_run, diff_scanner):
    # Mock successful git execution
    mock_run.side_effect = [
        MagicMock(returncode=0),  # check ref
        MagicMock(returncode=0, stdout="src/app.py\nsrc/utils.py\nREADME.md"),  # diff
    ]

    files = diff_scanner.get_changed_files("main")

    assert len(files) == 2
    assert any("src/app.py" in f for f in files)
    assert any("src/utils.py" in f for f in files)
    # README.md should be filtered out (not .py)


def test_resolve_module_path(diff_scanner, tmp_path):
    # src/app.py exists from fixture

    # Direct mapping
    path = diff_scanner._resolve_module_path("src.app")
    assert path is not None
    assert path.endswith(os.path.join("src", "app.py"))

    # Non-existent
    assert diff_scanner._resolve_module_path("src.unknown") is None


def test_impact_computation(diff_scanner, tmp_path):
    # Setup dependencies:
    # src/app.py IMPORTS src.utils
    # src/utils.py IMPORTS src.core
    # Change in src.core should impact src.utils AND src.app

    graph = IRGraph()

    # Node in src/app.py importing src.utils
    app_node = IRNode(
        id="import1",
        kind="Import",
        span={
            "file": "src/app.py",
            "start_line": 1,
            "start_col": 0,
            "end_line": 1,
            "end_col": 10,
        },
        attrs={"names": ["src.utils"]},
        parent_id=None,
        scope_id=None,
    )
    graph.add_node(app_node)

    # Node in src/utils.py importing src.core
    utils_node = IRNode(
        id="import2",
        kind="Import",
        span={
            "file": "src/utils.py",
            "start_line": 1,
            "start_col": 0,
            "end_line": 1,
            "end_col": 10,
        },
        attrs={"names": ["src.core"]},
        parent_id=None,
        scope_id=None,
    )
    graph.add_node(utils_node)

    # Mock persistence loading
    diff_scanner.persistence.load_project_graph = MagicMock(return_value=(graph, {}))

    # Change in src/core.py
    changed_core = str(tmp_path / "src/core.py")
    impacted = diff_scanner.compute_impacted_files([changed_core])

    # Should contain core.py (changed), utils.py (direct dep), app.py (transitive dep)
    assert len(impacted) == 3
    assert any("core.py" in f for f in impacted)
    assert any("utils.py" in f for f in impacted)
    assert any("app.py" in f for f in impacted)

    # Change in src/app.py (leaf)
    changed_app = str(tmp_path / "src/app.py")
    impacted_leaf = diff_scanner.compute_impacted_files([changed_app])

    assert len(impacted_leaf) == 1
    assert any("app.py" in f for f in impacted_leaf)

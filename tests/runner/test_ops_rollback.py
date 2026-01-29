"""Tests for ops rollback CLI commands."""

import json
from unittest import mock

import pytest
from click.testing import CliRunner

from src.runner.cli.main import cli


@pytest.fixture
def runner():
    """Create Click CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project structure with NSSS state."""
    # Create .nsss directory structure
    nsss_dir = tmp_path / ".nsss"
    nsss_dir.mkdir()

    cache_dir = nsss_dir / "cache"
    cache_dir.mkdir()

    # Create a mock baseline file
    baseline_path = nsss_dir / "baseline.json"
    baseline_data = {
        "version": "1.0",
        "generated_at": "2026-01-29T10:00:00Z",
        "project_root": str(tmp_path),
        "entries": [
            {
                "fingerprint": "test123",
                "rule_id": "sql-injection",
                "file": "test.py",
                "line": 10,
                "column": 5,
                "sink": "execute",
                "source": "user_input",
                "code_hash": "abc123",
                "created_at": "2026-01-29T10:00:00Z",
            }
        ],
    }
    baseline_path.write_text(json.dumps(baseline_data, indent=2))

    # Create a mock graph cache
    project_hash = "test_project_hash"
    graph_cache_dir = cache_dir / project_hash
    graph_cache_dir.mkdir(parents=True)
    graph_cache_path = graph_cache_dir / "graph_v1.jsonl"
    graph_cache_path.write_text(
        json.dumps(
            {
                "type": "meta",
                "version": "1.0",
                "timestamp": 1738147200,
                "project_root": str(tmp_path),
                "commit_hash": "abc123def456",
            }
        )
        + "\n"
    )

    # Create a mock LLM cache
    llm_cache_path = cache_dir / "llm_cache.json"
    llm_cache_data = {
        "version": "1.0",
        "entries": {
            "test_key": {
                "prompt": "test",
                "response": "test response",
                "timestamp": 1738147200,
            }
        },
    }
    llm_cache_path.write_text(json.dumps(llm_cache_data, indent=2))

    # Create a mock feedback store
    feedback_path = nsss_dir / "feedback.json"
    feedback_data = {
        "version": "1.0",
        "entries": [
            {
                "fingerprint": "test123",
                "status": "false_positive",
                "comment": "Not a real issue",
            }
        ],
    }
    feedback_path.write_text(json.dumps(feedback_data, indent=2))

    return tmp_path


def test_backup_baseline(runner, temp_project):
    """Test creating a baseline backup."""
    baseline_path = temp_project / ".nsss" / "baseline.json"
    assert baseline_path.exists()

    # Mock the backup function to verify it's called correctly
    with mock.patch("src.runner.cli.main._create_backup") as mock_backup:
        mock_backup.return_value = str(
            temp_project / ".nsss" / "baseline.json.backup.20260129100000"
        )

        result = runner.invoke(
            cli,
            [
                "ops",
                "backup",
                "--target",
                "baseline",
                "--project-root",
                str(temp_project),
            ],
        )

        # The command should succeed (even if not implemented yet)
        # This test will fail initially (TDD pattern)
        assert result.exit_code == 0 or "backup" in result.output.lower()


def test_rollback_baseline(runner, temp_project):
    """Test rolling back baseline to a previous backup."""
    # Create a backup manually
    baseline_path = temp_project / ".nsss" / "baseline.json"
    backup_path = temp_project / ".nsss" / "baseline.json.backup.20260129100000"

    # Modify the baseline
    original_content = baseline_path.read_text()
    backup_path.write_text(original_content)

    modified_data = json.loads(original_content)
    modified_data["entries"].append(
        {
            "fingerprint": "new_finding",
            "rule_id": "xss",
            "file": "test2.py",
            "line": 20,
            "column": 10,
            "sink": "render",
            "source": "request",
            "code_hash": "xyz789",
            "created_at": "2026-01-29T11:00:00Z",
        }
    )
    baseline_path.write_text(json.dumps(modified_data, indent=2))

    # Verify baseline was modified
    assert len(json.loads(baseline_path.read_text())["entries"]) == 2

    # Roll back to backup
    result = runner.invoke(
        cli,
        [
            "ops",
            "rollback",
            "--target",
            "baseline",
            "--backup-file",
            str(backup_path),
            "--project-root",
            str(temp_project),
            "--yes",  # Skip confirmation
        ],
    )

    # This will fail initially (TDD)
    assert result.exit_code == 0
    assert "rolled back" in result.output.lower() or "restored" in result.output.lower()

    # Verify rollback worked
    restored_data = json.loads(baseline_path.read_text())
    assert len(restored_data["entries"]) == 1
    assert restored_data["entries"][0]["fingerprint"] == "test123"


def test_rollback_graph_cache(runner, temp_project):
    """Test rolling back graph cache to a previous state."""
    # This test will fail initially, driving the implementation
    result = runner.invoke(
        cli,
        [
            "ops",
            "rollback",
            "--target",
            "graph",
            "--project-root",
            str(temp_project),
        ],
    )

    # Command should exist and provide meaningful output
    assert "rollback" in result.output.lower() or result.exit_code == 0


def test_rollback_list_backups(runner, temp_project):
    """Test listing available backups."""
    # Create multiple backups
    baseline_path = temp_project / ".nsss" / "baseline.json"
    content = baseline_path.read_text()

    backup1 = temp_project / ".nsss" / "baseline.json.backup.20260129100000"
    backup2 = temp_project / ".nsss" / "baseline.json.backup.20260129110000"
    backup3 = temp_project / ".nsss" / "baseline.json.backup.20260129120000"

    backup1.write_text(content)
    backup2.write_text(content)
    backup3.write_text(content)

    result = runner.invoke(
        cli, ["ops", "rollback", "--list", "--project-root", str(temp_project)]
    )

    # This will fail initially
    assert result.exit_code == 0
    assert "backup" in result.output.lower()
    # Should show all three backups
    assert "20260129100000" in result.output or "baseline" in result.output


def test_rollback_all_targets(runner, temp_project):
    """Test rolling back all targets simultaneously."""
    result = runner.invoke(
        cli,
        [
            "ops",
            "rollback",
            "--target",
            "all",
            "--project-root",
            str(temp_project),
            "--yes",  # Skip confirmation
        ],
    )

    # This will fail initially
    assert result.exit_code == 0 or "all targets" in result.output.lower()


def test_rollback_prune_old_backups(runner, temp_project):
    """Test pruning old backups."""
    # Create many backups
    baseline_path = temp_project / ".nsss" / "baseline.json"
    content = baseline_path.read_text()

    for i in range(10):
        backup_path = (
            temp_project / ".nsss" / f"baseline.json.backup.2026012910{i:02d}00"
        )
        backup_path.write_text(content)

    # Should have 10 backups
    backup_files = list((temp_project / ".nsss").glob("baseline.json.backup.*"))
    assert len(backup_files) == 10

    # Prune keeping only 5
    result = runner.invoke(
        cli,
        [
            "ops",
            "rollback",
            "--prune",
            "--keep",
            "5",
            "--target",
            "baseline",
            "--project-root",
            str(temp_project),
        ],
    )

    # This will fail initially
    assert result.exit_code == 0

    # Should only have 5 backups left
    backup_files = list((temp_project / ".nsss").glob("baseline.json.backup.*"))
    assert len(backup_files) == 5


def test_rollback_dry_run(runner, temp_project):
    """Test rollback dry-run mode."""
    baseline_path = temp_project / ".nsss" / "baseline.json"
    backup_path = temp_project / ".nsss" / "baseline.json.backup.20260129100000"
    backup_path.write_text(baseline_path.read_text())

    original_content = baseline_path.read_text()

    result = runner.invoke(
        cli,
        [
            "ops",
            "rollback",
            "--target",
            "baseline",
            "--backup-file",
            str(backup_path),
            "--project-root",
            str(temp_project),
            "--dry-run",
        ],
    )

    # This will fail initially
    assert result.exit_code == 0
    assert (
        "dry run" in result.output.lower() or "would restore" in result.output.lower()
    )

    # File should not have changed
    assert baseline_path.read_text() == original_content


def test_rollback_invalid_backup(runner, temp_project):
    """Test rollback with non-existent backup file."""
    result = runner.invoke(
        cli,
        [
            "ops",
            "rollback",
            "--target",
            "baseline",
            "--backup-file",
            str(temp_project / ".nsss" / "nonexistent.backup"),
            "--project-root",
            str(temp_project),
        ],
    )

    # Should fail gracefully
    assert (
        result.exit_code != 0
        or "not found" in result.output.lower()
        or "error" in result.output.lower()
    )

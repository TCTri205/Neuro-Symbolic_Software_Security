import os
import json
import subprocess
import shutil
import pytest
import tempfile
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
CLI_PATH = PROJECT_ROOT / "src" / "runner" / "cli" / "main.py"


@pytest.fixture
def temp_workspace():
    """Creates a temporary workspace for the test."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


def run_cli(args, cwd):
    """Runs the NSSS CLI."""
    cmd = ["python", str(CLI_PATH)] + args
    # Set python path to include project root
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=env)
    return result


def test_baseline_end_to_end(temp_workspace):
    """
    Test the full baseline workflow:
    1. Scan -> Generate Baseline
    2. Re-scan -> Verify 0 new findings
    3. Modify -> Verify 1 new finding
    """
    # Setup: Create a vulnerable file
    vuln_file = temp_workspace / "vuln.py"
    # Use a hardcoded secret that SecretScanner will catch
    vuln_code_v1 = """
def connect():
    api_key = "AIzaSyD-1234567890abcdef1234567890abcde" # Google API Key pattern
    print(api_key)
"""
    vuln_file.write_text(vuln_code_v1, encoding="utf-8")

    # Step 1: Generate Baseline
    # using --baseline flag
    args_1 = ["scan", str(vuln_file), "--baseline"]
    res_1 = run_cli(args_1, temp_workspace)
    assert res_1.returncode == 0, f"Baseline generation failed: {res_1.stderr}"

    baseline_path = temp_workspace / ".nsss" / "baseline.json"
    assert baseline_path.exists(), "Baseline file not created"

    # Load baseline to verify content
    baseline_data = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert (
        len(baseline_data.get("entries", [])) > 0
    ), f"Baseline entries empty: {baseline_data}"

    # Step 2: Re-scan with --baseline-only (Diff Mode)
    # Should report 0 findings because nothing changed
    args_2 = [
        "scan",
        str(vuln_file),
        "--baseline-only",
        "--format",
        "json",
        "--report-type",
        "markdown",
    ]
    res_2 = run_cli(args_2, temp_workspace)
    assert res_2.returncode == 0

    # Check debug stats
    debug_path = temp_workspace / "nsss_debug.json"
    assert debug_path.exists(), "Debug file should exist"
    debug_data = json.loads(debug_path.read_text(encoding="utf-8"))

    # Verify stats
    assert debug_data["baseline"]["new"] == 0
    assert debug_data["baseline"]["existing"] >= 1

    # Check Markdown Report for Summary
    report_path_md = temp_workspace / "nsss_report.md"
    assert report_path_md.exists()
    md_content = report_path_md.read_text(encoding="utf-8")
    assert "## Baseline Summary" in md_content
    assert "**New Findings**: 0" in md_content

    # Step 3: Modify Code (Add new vuln)

    vuln_code_v2 = """
def connect():
    api_key = "AIzaSyD-1234567890abcdef1234567890abcde" # Google API Key pattern
    
    # Add another secret (New)
    aws_key = "AKIA1234567890ABCDEF" 
    print(aws_key)
"""
    vuln_file.write_text(vuln_code_v2, encoding="utf-8")

    # Step 4: Scan again with --baseline-only
    args_3 = [
        "scan",
        str(vuln_file),
        "--baseline-only",
        "--format",
        "json",
    ]
    res_3 = run_cli(args_3, temp_workspace)
    assert res_3.returncode == 0

    # Verify nsss_debug.json again
    debug_data_2 = json.loads(debug_path.read_text(encoding="utf-8"))

    # Should have 1 new, 1 existing
    assert debug_data_2["baseline"]["new"] == 1, "Should report 1 new finding"
    assert debug_data_2["baseline"]["existing"] >= 1, "Should report existing finding"

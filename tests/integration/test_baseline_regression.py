import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent.parent
CLI_PATH = PROJECT_ROOT / "src" / "runner" / "cli" / "main.py"


@pytest.fixture
def temp_workspace():
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


def run_cli(args, cwd):
    cmd = ["python", str(CLI_PATH)] + args
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=env)


def test_baseline_resolved_when_issue_fixed(temp_workspace):
    vuln_file = temp_workspace / "vuln.py"
    vuln_code = """
def connect():
    api_key = "AIzaSyD-1234567890abcdef1234567890abcde"
    print(api_key)
"""
    vuln_file.write_text(vuln_code, encoding="utf-8")

    res_1 = run_cli(["scan", str(vuln_file), "--baseline"], temp_workspace)
    assert res_1.returncode == 0, f"Baseline generation failed: {res_1.stderr}"

    baseline_path = temp_workspace / ".nsss" / "baseline.json"
    assert baseline_path.exists(), "Baseline file not created"

    fixed_code = """
def connect():
    print("no secrets here")
"""
    vuln_file.write_text(fixed_code, encoding="utf-8")

    res_2 = run_cli(
        ["scan", str(vuln_file), "--baseline-only", "--format", "json"],
        temp_workspace,
    )
    assert res_2.returncode == 0, f"Baseline scan failed: {res_2.stderr}"

    debug_path = temp_workspace / "nsss_debug.json"
    assert debug_path.exists(), "Debug output not generated"
    debug_data = json.loads(debug_path.read_text(encoding="utf-8"))

    stats = debug_data["baseline"]
    assert stats["new"] == 0
    assert stats["existing"] == 0
    assert stats["total"] >= 1
    assert stats["resolved"] == stats["total"]

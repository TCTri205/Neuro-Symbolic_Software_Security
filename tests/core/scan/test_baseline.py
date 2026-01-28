import os
from src.core.scan.baseline import BaselineEngine


def test_fingerprint_stable_across_whitespace(tmp_path):
    storage_path = os.path.join(tmp_path, "baseline.json")
    engine = BaselineEngine(storage_path=storage_path, project_root=str(tmp_path))

    finding = {
        "check_id": "TEST.RULE",
        "line": 3,
        "column": 5,
        "sink": "eval",
        "source": "user_input",
    }

    code_a = "def main():\n    x = 1\n    eval(x)\n"
    code_b = "def main():\n    x = 1  \n    eval(x)   \n"

    fingerprint_a = engine.fingerprint_for_finding(
        finding, "src/app.py", code_a.splitlines()
    )
    fingerprint_b = engine.fingerprint_for_finding(
        finding, "src/app.py", code_b.splitlines()
    )

    assert fingerprint_a == fingerprint_b


def test_fingerprint_changes_when_logic_changes(tmp_path):
    storage_path = os.path.join(tmp_path, "baseline.json")
    engine = BaselineEngine(storage_path=storage_path, project_root=str(tmp_path))

    finding = {
        "check_id": "TEST.RULE",
        "line": 3,
        "column": 5,
        "sink": "eval",
        "source": "user_input",
    }

    code_a = "def main():\n    x = 1\n    eval(x)\n"
    code_b = "def main():\n    x = 1\n    eval(y)\n"

    fingerprint_a = engine.fingerprint_for_finding(
        finding, "src/app.py", code_a.splitlines()
    )
    fingerprint_b = engine.fingerprint_for_finding(
        finding, "src/app.py", code_b.splitlines()
    )

    assert fingerprint_a != fingerprint_b


def test_filter_findings_suppresses_existing(tmp_path):
    storage_path = os.path.join(tmp_path, "baseline.json")
    finding = {
        "check_id": "TEST.RULE",
        "line": 3,
        "column": 5,
        "sink": "eval",
        "source": "user_input",
    }
    code = "def main():\n    x = 1\n    eval(x)\n"
    source_lines = code.splitlines()

    engine = BaselineEngine(storage_path=storage_path, project_root=str(tmp_path))
    entries = engine.build_entries([finding], "src/app.py", source_lines)
    engine.save(entries)

    reloaded = BaselineEngine(storage_path=storage_path, project_root=str(tmp_path))
    filtered, stats = reloaded.filter_findings([finding], "src/app.py", source_lines)

    assert filtered == []
    assert stats["existing"] == 1
    assert stats["new"] == 0

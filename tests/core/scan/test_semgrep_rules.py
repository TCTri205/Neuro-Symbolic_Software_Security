import os
import json
from unittest.mock import patch, MagicMock
from src.core.scan.engine import RuleEngine

# Mock output matching Semgrep JSON format
MOCK_SEMGREP_OUTPUT = {
    "results": [
        {
            "check_id": "cwe-78-os-injection",
            "path": "test_vuln.py",
            "start": {"line": 10, "col": 5},
            "extra": {
                "message": "Potential OS Command Injection (CWE-78)",
                "severity": "ERROR",
                "metadata": {"cwe": "CWE-78"},
            },
        },
        {
            "check_id": "cwe-502-deserialization",
            "path": "test_vuln.py",
            "start": {"line": 15, "col": 5},
            "extra": {
                "message": "Unsafe deserialization (CWE-502)",
                "severity": "ERROR",
                "metadata": {"cwe": "CWE-502"},
            },
        },
    ]
}


def test_rule_engine_scan(tmp_path):
    # Create a dummy file (content doesn't matter because we mock output)
    vuln_file = tmp_path / "test_vuln.py"
    vuln_file.write_text("import os; os.system('ls')")

    # Mock subprocess.run inside SemgrepRunner
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(MOCK_SEMGREP_OUTPUT)
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Initialize Engine
        engine = RuleEngine()

        # Verify the default rule path exists (it should, as we created it)
        assert os.path.exists(engine.rules_path)

        findings = engine.scan_file(str(vuln_file))

        assert len(findings) == 2
        assert findings[0].check_id == "cwe-78-os-injection"
        assert findings[0].severity == "ERROR"
        assert findings[1].check_id == "cwe-502-deserialization"

        # Verify semgrep was called with correct arguments
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "semgrep"
        assert "--json" in args
        assert "--config" in args
        # Ensure it points to our custom rules
        assert engine.rules_path in args

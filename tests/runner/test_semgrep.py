import os
import tempfile
import unittest
from unittest.mock import patch

from src.core.pipeline.orchestrator import AnalysisOrchestrator
from src.runner.tools.semgrep import SemgrepRunner


class TestSemgrepIntegration(unittest.TestCase):
    def test_semgrep_findings_mapped_to_blocks(self):
        code = """
def foo():
    x = 1
    return x

foo()
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, "sample.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            mock_output = {
                "results": [
                    {
                        "check_id": "TEST.RULE",
                        "path": file_path,
                        "start": {"line": 3, "col": 5},
                        "extra": {"message": "bad pattern", "severity": "WARNING"},
                    }
                ]
            }

            with patch("src.core.pipeline.orchestrator.SemgrepRunner") as mock_runner:
                mock_runner.return_value.run.return_value = mock_output
                orchestrator = AnalysisOrchestrator()
                res = orchestrator.analyze_file(file_path)
                result = res.to_dict()

            blocks = result["structure"]["blocks"]
            blocks_with_findings = [b for b in blocks if b["security_findings"]]

            self.assertEqual(len(blocks_with_findings), 1)
            self.assertEqual(
                blocks_with_findings[0]["security_findings"][0]["check_id"], "TEST.RULE"
            )
            self.assertEqual(result["semgrep"]["results"][0]["check_id"], "TEST.RULE")

    def test_semgrep_runner_handles_missing_binary(self):
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            runner = SemgrepRunner()
            result = runner.run("dummy.py")
        self.assertEqual(result["error"], "semgrep not installed")
        self.assertEqual(result["results"], [])


if __name__ == "__main__":
    unittest.main()

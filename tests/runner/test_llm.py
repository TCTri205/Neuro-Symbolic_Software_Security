import os
import tempfile
import unittest
import json
from unittest.mock import patch

from src.core.pipeline.orchestrator import AnalysisOrchestrator


class TestLLMIntegration(unittest.TestCase):
    def test_llm_insights_added_to_blocks(self):
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

            mock_semgrep = {
                "results": [
                    {
                        "check_id": "TEST.RULE",
                        "path": file_path,
                        "start": {"line": 3, "col": 5},
                        "extra": {"message": "bad pattern", "severity": "WARNING"},
                    }
                ]
            }

            with patch(
                "src.core.pipeline.orchestrator.SemgrepRunner"
            ) as mock_runner, patch(
                "src.core.pipeline.orchestrator.LLMClient"
            ) as mock_llm:
                mock_runner.return_value.run.return_value = mock_semgrep

                llm_instance = mock_llm.return_value
                llm_instance.is_configured = True
                llm_instance.provider = "openai"
                llm_instance.model = "gpt-5.2-codex"
                llm_instance.chat.return_value = {"content": '{"analysis": []}'}

                orchestrator = AnalysisOrchestrator()
                res = orchestrator.analyze_file(file_path)
                result = res.to_dict()

            blocks = result["structure"]["blocks"]
            blocks_with_insights = [b for b in blocks if b["llm_insights"]]

            self.assertEqual(len(blocks_with_insights), 1)
            self.assertEqual(
                blocks_with_insights[0]["llm_insights"][0]["provider"], "openai"
            )
            args, _ = llm_instance.chat.call_args
            messages = args[0]
            self.assertTrue(
                any(
                    "SSA context" in message.get("content", "")
                    for message in messages
                    if message.get("role") == "user"
                )
            )

    def test_remediation_requested_and_stored(self):
        code = """
def insecure():
    eval("1+1")
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, "vulnerable.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            mock_semgrep = {
                "results": [
                    {
                        "check_id": "python.lang.security.audit.eval-detected.eval-detected",
                        "path": file_path,
                        "start": {"line": 3, "col": 5},
                        "extra": {"message": "eval detected", "severity": "WARNING"},
                    }
                ]
            }

            mock_llm_response = {
                "content": json.dumps(
                    {
                        "analysis": [
                            {
                                "check_id": "python.lang.security.audit.eval-detected.eval-detected",
                                "verdict": "true positive",
                                "rationale": "eval is dangerous",
                                "remediation": "Use ast.literal_eval",
                            }
                        ]
                    }
                )
            }

            with patch(
                "src.core.pipeline.orchestrator.SemgrepRunner"
            ) as mock_runner, patch(
                "src.core.pipeline.orchestrator.LLMClient"
            ) as mock_llm:
                mock_runner.return_value.run.return_value = mock_semgrep

                llm_instance = mock_llm.return_value
                llm_instance.is_configured = True
                llm_instance.provider = "openai"
                llm_instance.model = "gpt-4o"
                llm_instance.chat.return_value = mock_llm_response

                orchestrator = AnalysisOrchestrator()
                res = orchestrator.analyze_file(file_path)
                result = res.to_dict()

            blocks = result["structure"]["blocks"]
            blocks_with_findings = [b for b in blocks if b["security_findings"]]
            self.assertEqual(len(blocks_with_findings), 1)

            # Check prompt contains "remediation"
            args, _ = llm_instance.chat.call_args
            messages = args[0]
            user_msg = next(m["content"] for m in messages if m["role"] == "user")
            self.assertIn(
                "Provide a concise rationale and a specific code remediation", user_msg
            )
            self.assertIn("'remediation'", user_msg)

            # Check result stored and parsed
            insight = blocks_with_findings[0]["llm_insights"][0]
            self.assertEqual(insight["response"], mock_llm_response["content"])

            # Verify parsing
            self.assertIn("analysis", insight)
            self.assertEqual(len(insight["analysis"]), 1)
            self.assertEqual(
                insight["analysis"][0]["remediation"], "Use ast.literal_eval"
            )


if __name__ == "__main__":
    unittest.main()

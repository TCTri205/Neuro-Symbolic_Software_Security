import os
import tempfile
import unittest
from unittest.mock import patch

from src.runner.pipeline.orchestrator import Pipeline


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

            with patch("src.runner.pipeline.orchestrator.SemgrepRunner") as mock_runner, patch(
                "src.runner.pipeline.orchestrator.LLMClient"
            ) as mock_llm:
                mock_runner.return_value.run.return_value = mock_semgrep

                llm_instance = mock_llm.return_value
                llm_instance.is_configured = True
                llm_instance.provider = "openai"
                llm_instance.model = "gpt-5.2-codex"
                llm_instance.chat.return_value = {"content": "{\"analysis\": []}"}

                pipeline = Pipeline()
                pipeline.scan_file(file_path)

            result = pipeline.results[file_path]
            blocks = result["structure"]["blocks"]
            blocks_with_insights = [b for b in blocks if b["llm_insights"]]

            self.assertEqual(len(blocks_with_insights), 1)
            self.assertEqual(blocks_with_insights[0]["llm_insights"][0]["provider"], "openai")
            args, _ = llm_instance.chat.call_args
            messages = args[0]
            self.assertTrue(
                any(
                    "SSA context" in message.get("content", "")
                    for message in messages
                    if message.get("role") == "user"
                )
            )


if __name__ == "__main__":
    unittest.main()

import os
import os
import unittest
import tempfile
import json
from unittest.mock import patch

from src.librarian.core import Librarian
from src.core.pipeline.orchestrator import AnalysisOrchestrator


class TestLibrarianCore(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_librarian.db")
        self.librarian = Librarian(self.db_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_store_and_query(self):
        prompt = [{"role": "user", "content": "test prompt"}]
        response_content = json.dumps({"analysis": [{"verdict": "false positive"}]})
        analysis_data = [{"verdict": "false positive"}]
        model = "test-model"

        # Initially should be empty
        self.assertIsNone(self.librarian.query(prompt))

        # Store
        self.librarian.store(prompt, response_content, analysis_data, model)

        # Query
        result = self.librarian.query(prompt)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result["cached"])
        self.assertEqual(result["model"], model)
        self.assertEqual(result["response"], response_content)
        self.assertEqual(result["analysis"][0]["verdict"], "false positive")

    def test_hash_stability(self):
        prompt1 = [{"role": "user", "content": "A"}]
        prompt2 = [{"role": "user", "content": "A"}]
        prompt3 = [{"role": "user", "content": "B"}]

        self.assertEqual(
            self.librarian.compute_hash(prompt1), self.librarian.compute_hash(prompt2)
        )
        self.assertNotEqual(
            self.librarian.compute_hash(prompt1), self.librarian.compute_hash(prompt3)
        )

    def test_profile_management(self):
        # Add a profile for Flask 2.x
        self.librarian.add_profile(
            "flask", ">=2.0.0, <3.0.0", "sink", "flask.request.args", {"risk": "high"}
        )

        # Test matching version
        profiles_2_1 = self.librarian.get_profiles("flask", "2.1.0")
        self.assertEqual(len(profiles_2_1), 1)
        self.assertEqual(profiles_2_1[0]["identifier"], "flask.request.args")

        # Test non-matching version
        profiles_1_0 = self.librarian.get_profiles("flask", "1.0.0")
        self.assertEqual(len(profiles_1_0), 0)

        # Test wildcard (no spec)
        self.librarian.add_profile("flask", "", "info", "general_info")
        profiles_wildcard = self.librarian.get_profiles("flask", "1.0.0")
        self.assertEqual(len(profiles_wildcard), 1)
        self.assertEqual(profiles_wildcard[0]["identifier"], "general_info")


class TestLibrarianIntegration(unittest.TestCase):
    def setUp(self):
        # We need to patch the default DB path for the pipeline's librarian
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "integration_test.db")

    def tearDown(self):
        self.tmp_dir.cleanup()
        if os.path.exists("nsss_librarian.db"):
            # Cleanup default db if created by accident
            try:
                os.remove("nsss_librarian.db")
            except OSError:
                pass

    @patch("src.core.pipeline.orchestrator.Librarian")
    def test_pipeline_caches_results(self, MockLibrarian):
        # Setup the mock to behave like a real librarian but with our temp db
        real_librarian = Librarian(self.db_path)
        MockLibrarian.return_value = real_librarian

        code = """
def foo():
    x = 1
    return x
"""
        with tempfile.TemporaryDirectory() as code_dir:
            file_path = os.path.join(code_dir, "target.py")
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

            mock_llm_response = {
                "content": json.dumps(
                    {
                        "analysis": [
                            {
                                "check_id": "TEST.RULE",
                                "verdict": "true positive",
                                "rationale": "it is bad",
                                "remediation": "fix it",
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
                llm_instance.model = "gpt-4"
                llm_instance.chat.return_value = mock_llm_response

                # FIRST RUN
                orchestrator1 = AnalysisOrchestrator()
                # Ensure it's using our real_librarian (patched)
                self.assertEqual(orchestrator1.librarian, real_librarian)

                res1 = orchestrator1.analyze_file(file_path)
                result1 = res1.to_dict()

                # Check results
                # Find block with insights
                blocks_with_insights = [
                    b for b in result1["structure"]["blocks"] if b["llm_insights"]
                ]
                self.assertEqual(len(blocks_with_insights), 1)
                insight1 = blocks_with_insights[0]["llm_insights"][0]
                self.assertNotIn("cached", insight1)  # First run not cached

                # Verify LLM was called
                llm_instance.chat.assert_called()
                call_count_after_first = llm_instance.chat.call_count

                # SECOND RUN - Should hit cache
                orchestrator2 = AnalysisOrchestrator()
                # Ensure it's using the SAME real_librarian (patched return value)
                # (MockLibrarian return value is consistent)

                res2 = orchestrator2.analyze_file(file_path)
                result2 = res2.to_dict()

                blocks_with_insights_2 = [
                    b for b in result2["structure"]["blocks"] if b["llm_insights"]
                ]
                insight2 = blocks_with_insights_2[0]["llm_insights"][0]

                self.assertTrue(insight2.get("cached"))
                self.assertEqual(insight2["provider"], "librarian")

                # Verify LLM was NOT called again
                self.assertEqual(llm_instance.chat.call_count, call_count_after_first)


if __name__ == "__main__":
    unittest.main()

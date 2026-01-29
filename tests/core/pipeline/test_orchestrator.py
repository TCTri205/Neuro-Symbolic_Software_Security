import json
from unittest.mock import patch

from src.core.persistence import build_file_cache_path
from src.core.pipeline.orchestrator import AnalysisOrchestrator


class TestAnalysisOrchestrator:
    def setup_method(self):
        self.orchestrator = AnalysisOrchestrator()

    def test_full_pipeline_success(self):
        # Code containing a secret, some logic for CFG, and identifiers for masking
        # Use a fake AWS key pattern to ensure detection
        code = """
def main():
    aws_key = "AKIA1234567890ABCDEF"
    if aws_key:
        print("Connected")
    else:
        print("Error")
"""
        result = self.orchestrator.analyze_code(code, "test.py")

        # Check Secret Scanning
        assert len(result.secrets) > 0
        assert "AWS" in result.secrets[0].type

        # Check CFG
        assert result.cfg is not None
        # Check simple property of CFG (e.g., number of blocks > 1)
        # Assuming CFG structure. If it's a dict or object, check appropriately.
        # Based on builder.py, it returns the `cfg` object which has `blocks`.
        assert len(result.cfg.nodes) > 0

        # Check Privacy Masking
        assert result.masked_code is not None
        assert "main" not in result.masked_code  # Should be masked to func_X
        assert "api_key" not in result.masked_code
        assert result.mask_mapping is not None

    def test_error_handling(self):
        # Invalid syntax code
        code = "def broken_code(: print("

        result = self.orchestrator.analyze_code(code, "broken.py")

        # CFG and Masker likely fail on syntax error
        assert len(result.errors) > 0
        # Secret scanner might still run on raw string?
        # Regex scanner runs on raw string, so it might succeed.
        # Entropy scanner uses AST? If AST based, it fails.
        # Let's check that we didn't crash and got an error report.
        assert result.cfg is None or len(result.errors) > 0

    @patch("src.core.pipeline.orchestrator.SemgrepRunner")
    @patch("src.core.pipeline.orchestrator.LLMClient")
    def test_advanced_features(self, MockLLM, MockSemgrep):
        # Mock Semgrep
        MockSemgrep.return_value.run.return_value = {
            "results": [
                {
                    "check_id": "TEST.RULE",
                    "path": "advanced.py",
                    "start": {"line": 3, "col": 5},
                    "extra": {"message": "bad", "severity": "ERROR"},
                }
            ]
        }

        # Mock LLM
        llm_instance = MockLLM.return_value
        llm_instance.is_configured = True
        llm_instance.model = "gpt-4-mock"
        llm_instance.chat.return_value = {
            "content": '{"analysis": [{"verdict": "True Positive"}]}'
        }

        # Instantiate here to use mocks
        orchestrator = AnalysisOrchestrator()

        code = """
def main():
    x = 1
    eval(x)
"""
        result = orchestrator.analyze_code(code, "advanced.py")

        # Check Semgrep integration
        assert result.semgrep_results is not None
        assert len(result.semgrep_results["results"]) == 1

        # Check Call Graph
        assert result.call_graph is not None
        # main definition should be in call graph (or at least definitions extracted)

        # Check SSA
        assert result.ssa is not None
        assert len(result.ssa.vars) > 0

        # Check LLM Insights
        # We need to find the block that corresponds to line 3 (eval)
        # and see if insights were added.
        assert result.cfg is not None
        has_insights = False
        for block in result.cfg._blocks.values():
            if block.llm_insights:
                has_insights = True
                assert (
                    block.llm_insights[0]["analysis"][0]["verdict"] == "True Positive"
                )

        assert has_insights

    def test_ir_graph_persistence_writes_cache(self, tmp_path, monkeypatch):
        code = """
def main():
    return 1
"""
        monkeypatch.chdir(tmp_path)
        orchestrator = AnalysisOrchestrator(enable_ir=True)
        result = orchestrator.analyze_code(code, "sample.py")

        assert result.ir is not None
        cache_path = build_file_cache_path(str(tmp_path), "sample.py")
        with open(cache_path, "r", encoding="utf-8") as f:
            meta = json.loads(f.readline())
        assert meta["type"] == "meta"
        assert meta["file_path"] == "sample.py"

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

from src.core.ai.protocol import AnalysisRequest, AnalysisResponse


class TestProtocolSchema:
    def test_analysis_request_valid(self):
        payload = {
            "function_signature": "def foo(): pass",
            "language": "python",
            "vulnerability_type": "sqli",
            "context": {"source_variable": "x", "line_number": 10},
            "privacy_mask": {"enabled": True, "map": {"FUNC_1": "my_func"}},
            "metadata": {"mode": "precision", "request_id": "123"},
        }
        req = AnalysisRequest(**payload)
        assert req.function_signature == "def foo(): pass"
        assert req.context.line_number == 10
        assert req.privacy_mask.enabled is True

    def test_analysis_response_valid(self):
        payload = {
            "status": "success",
            "data": {
                "is_vulnerable": True,
                "confidence_score": 0.95,
                "risk_level": "CRITICAL",
                "reasoning_trace": "Because...",
                "analysis_summary": "Bad code",
                "constraint_check": {"syntax_valid": True, "logic_sound": True},
            },
            "processing_time_ms": 100.5,
        }
        res = AnalysisResponse(**payload)
        assert res.status == "success"
        assert res.data.is_vulnerable is True
        assert res.data.constraint_check.syntax_valid is True

    def test_analysis_response_error(self):
        payload = {
            "status": "error",
            "error_code": "CONTEXT_TOO_LONG",
            "message": "Too long",
        }
        res = AnalysisResponse(**payload)
        assert res.status == "error"
        assert res.data is None
        assert res.error_code == "CONTEXT_TOO_LONG"

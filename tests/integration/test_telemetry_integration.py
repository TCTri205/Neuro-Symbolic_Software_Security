import pytest
from src.core.pipeline.orchestrator import AnalysisOrchestrator
from src.core.telemetry import MetricsCollector

CODE_SAMPLE = """
def hello():
    print("Hello world")
    secret = "sk-1234567890abcdef1234567890abcdef"
"""


def test_pipeline_telemetry():
    # Reset metrics
    collector = MetricsCollector()
    collector.reset()

    orchestrator = AnalysisOrchestrator()
    result = orchestrator.analyze_code(CODE_SAMPLE, file_path="test_sample.py")

    # Verify result
    assert len(result.secrets) > 0
    assert result.cfg is not None
    assert result.masked_code is not None

    # Verify telemetry
    summary = collector.get_summary()
    latencies = summary["latency"]

    assert "scan_secrets" in latencies
    assert latencies["scan_secrets"]["count"] == 1

    assert "build_cfg" in latencies
    assert latencies["build_cfg"]["count"] == 1

    assert "privacy_masking" in latencies
    assert latencies["privacy_masking"]["count"] == 1


def test_ai_telemetry(monkeypatch):
    from src.core.ai.client import MockAIClient

    # Reset metrics
    collector = MetricsCollector()
    collector.reset()

    client = MockAIClient()
    response = client.analyze("system", "user")

    assert "MOCK_RESPONSE" in response

    summary = collector.get_summary()
    assert "ai_inference_mock" in summary["latency"]

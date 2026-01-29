import pytest
import time
import json
import os
from src.core.telemetry.metrics import MetricsCollector, MeasureLatency, FeedbackMetric


@pytest.fixture
def metrics_collector():
    collector = MetricsCollector()
    collector.reset()
    return collector


def test_singleton(metrics_collector):
    c2 = MetricsCollector()
    assert metrics_collector is c2


def test_track_tokens(metrics_collector):
    metrics_collector.track_tokens("gpt-4", 100, 50)
    metrics_collector.track_tokens("gpt-4", 200, 100)

    summary = metrics_collector.get_summary()
    assert summary["tokens"]["gpt-4"]["prompt"] == 300
    assert summary["tokens"]["gpt-4"]["completion"] == 150
    assert summary["tokens"]["gpt-4"]["total"] == 450


def test_track_latency(metrics_collector):
    metrics_collector.track_latency("scan", 100.0)
    metrics_collector.track_latency("scan", 200.0)

    summary = metrics_collector.get_summary()
    scan_stats = summary["latency"]["scan"]

    assert scan_stats["count"] == 2
    assert scan_stats["min"] == 100.0
    assert scan_stats["max"] == 200.0
    assert scan_stats["avg"] == 150.0


def test_measure_latency_context_manager(metrics_collector):
    with MeasureLatency("test_op"):
        time.sleep(0.01)

    summary = metrics_collector.get_summary()
    assert "test_op" in summary["latency"]
    assert summary["latency"]["test_op"]["count"] == 1
    assert summary["latency"]["test_op"]["min"] > 0


def test_dump_to_file(metrics_collector, tmp_path):
    metrics_collector.track_tokens("model", 10, 10)
    output_file = tmp_path / "metrics.json"

    metrics_collector.dump_to_file(str(output_file))

    assert os.path.exists(output_file)
    with open(output_file) as f:
        data = json.load(f)
        assert data["tokens"]["model"]["total"] == 20


def test_feedback_metric_precision():
    fm = FeedbackMetric(
        true_positives=8, false_positives=2, true_negatives=5, false_negatives=1
    )
    assert fm.precision == 0.8  # 8 / (8 + 2)
    assert fm.recall == 8 / 9  # 8 / (8 + 1)
    assert fm.fpr == 2 / 7  # 2 / (2 + 5)
    assert abs(fm.f1_score - 0.8421) < 0.001  # 2 * (0.8 * 0.889) / (0.8 + 0.889)


def test_feedback_metric_edge_cases():
    # All zeros
    fm = FeedbackMetric()
    assert fm.precision == 0.0
    assert fm.recall == 0.0
    assert fm.fpr == 0.0
    assert fm.f1_score == 0.0


def test_track_feedback(metrics_collector):
    metrics_collector.track_feedback("TRUE_POSITIVE")
    metrics_collector.track_feedback("TRUE_POSITIVE")
    metrics_collector.track_feedback("FALSE_POSITIVE")
    metrics_collector.track_feedback("TRUE_NEGATIVE")

    summary = metrics_collector.get_summary()
    fb = summary["feedback"]

    assert fb["true_positives"] == 2
    assert fb["false_positives"] == 1
    assert fb["true_negatives"] == 1
    assert fb["precision"] == round(2 / 3, 4)
    assert fb["fpr"] == round(1 / 2, 4)


def test_track_feedback_unknown_type(metrics_collector):
    """Unknown feedback types should be logged as warning but not crash."""
    metrics_collector.track_feedback("UNKNOWN_TYPE")
    summary = metrics_collector.get_summary()
    fb = summary["feedback"]

    # All should remain 0
    assert fb["true_positives"] == 0
    assert fb["false_positives"] == 0


def test_get_summary_with_all_metrics(metrics_collector):
    """Integration test: summary includes tokens, latency, and feedback."""
    metrics_collector.track_tokens("gpt-4", 100, 50)
    metrics_collector.track_latency("scan", 123.45)
    metrics_collector.track_feedback("TRUE_POSITIVE")
    metrics_collector.track_feedback("FALSE_POSITIVE")

    summary = metrics_collector.get_summary()

    assert "tokens" in summary
    assert "latency" in summary
    assert "feedback" in summary

    assert summary["tokens"]["gpt-4"]["total"] == 150
    assert summary["latency"]["scan"]["count"] == 1
    assert summary["feedback"]["true_positives"] == 1
    assert summary["feedback"]["false_positives"] == 1
    assert summary["feedback"]["precision"] == 0.5

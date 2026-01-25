import pytest
import time
import json
import os
from src.core.telemetry.metrics import MetricsCollector, MeasureLatency


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

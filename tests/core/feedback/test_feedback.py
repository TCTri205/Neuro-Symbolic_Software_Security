import pytest
import os
import tempfile
from src.core.feedback import (
    FeedbackService,
    FeedbackStore,
    FeedbackRequest,
    FeedbackType,
)
from src.core.risk.ranker import RankerService
from src.core.telemetry.metrics import MetricsCollector

from src.core.taint.engine import TaintFlow
from src.core.risk.schema import RiskLevel


@pytest.fixture
def temp_store_path():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_feedback_store_and_service(temp_store_path):
    store = FeedbackStore(storage_path=temp_store_path)
    service = FeedbackService(store=store)

    req = FeedbackRequest(
        check_id="TAINT_FLOW",
        metadata={"source": "input", "sink": "eval"},
        feedback_type=FeedbackType.FALSE_POSITIVE,
        comment="Test FP",
    )

    service.add_feedback(req)

    feedback = service.get_feedback("TAINT_FLOW", {"source": "input", "sink": "eval"})
    assert feedback is not None
    assert feedback.feedback_type == FeedbackType.FALSE_POSITIVE
    assert feedback.comment == "Test FP"


def test_ranker_integration_false_positive(temp_store_path):
    store = FeedbackStore(storage_path=temp_store_path)
    service = FeedbackService(store=store)
    ranker = RankerService(feedback_service=service)

    # Add FP feedback
    req = FeedbackRequest(
        check_id="TAINT_FLOW",
        metadata={"source": "user_input", "sink": "os.system", "path_length": 3},
        feedback_type=FeedbackType.FALSE_POSITIVE,
    )
    service.add_feedback(req)

    # Create flow matching feedback
    # Note: Signature relies on source, sink, file_path, line. Ranker passes source, sink, path_length.
    # We must match what Ranker passes.
    # In Ranker _score_flow:
    # metadata = { "source": ..., "sink": ..., "path": ..., "path_length": ..., "implicit": ... }
    # FeedbackService compute_signature uses source, sink, file_path, line.

    # Wait, Ranker does NOT pass file_path or line in _score_flow metadata yet!
    # I need to verify what metadata keys are shared.

    # In Ranker:
    # metadata = { "source": flow.source, "sink": flow.sink, "path": flow.path, "path_length": ... }

    # In FeedbackService.compute_signature:
    # if "source" in metadata: ...
    # if "sink" in metadata: ...
    # if "file_path" in metadata: ...
    # if "line" in metadata: ...

    # So if I add feedback with just source/sink/path_length, and Ranker calls with source/sink/path_length,
    # path_length is NOT used in compute_signature!

    # FeedbackService keys: check_id, source, sink, file_path, line.
    # Ranker keys: check_id, source, sink, path, path_length, implicit.

    # So only check_id, source, sink match.

    # Test update: Don't rely on path_length for signature yet unless I update signature logic.

    flow = TaintFlow(
        source="user_input", sink="os.system", path=["a", "b", "c"], implicit=False
    )

    # Rank
    output = ranker.rank([flow])
    item = output.items[0]

    assert item.risk.risk_level == RiskLevel.SAFE
    assert item.risk.risk_score == 0.0
    assert item.risk.summary is not None
    assert "Feedback Applied" in item.risk.summary
    assert any(s.name == "feedback_override" for s in item.signals)


def test_ranker_integration_adjust_risk(temp_store_path):
    store = FeedbackStore(storage_path=temp_store_path)
    service = FeedbackService(store=store)
    ranker = RankerService(feedback_service=service)

    # Add Adjust Risk feedback
    req = FeedbackRequest(
        check_id="TAINT_FLOW",
        metadata={"source": "user_input", "sink": "print"},
        feedback_type=FeedbackType.ADJUST_RISK,
        adjusted_score=90.0,
    )
    service.add_feedback(req)

    # Create flow
    flow = TaintFlow(source="user_input", sink="print", path=["a"], implicit=False)

    # Rank
    output = ranker.rank([flow])
    item = output.items[0]

    assert item.risk.risk_level == RiskLevel.CRITICAL
    assert item.risk.risk_score == 90.0
    assert any(s.name == "feedback_adjustment" for s in item.signals)


def test_feedback_service_metrics_integration(temp_store_path):
    """Test that FeedbackService tracks metrics when feedback is added."""
    metrics = MetricsCollector()
    metrics.reset()

    store = FeedbackStore(storage_path=temp_store_path)
    service = FeedbackService(store=store, metrics_collector=metrics)

    # Add TRUE_POSITIVE feedback
    req1 = FeedbackRequest(
        check_id="TAINT_FLOW",
        metadata={"source": "input", "sink": "eval"},
        feedback_type=FeedbackType.TRUE_POSITIVE,
    )
    service.add_feedback(req1)

    # Add FALSE_POSITIVE feedback
    req2 = FeedbackRequest(
        check_id="TAINT_FLOW",
        metadata={"source": "safe_input", "sink": "print"},
        feedback_type=FeedbackType.FALSE_POSITIVE,
    )
    service.add_feedback(req2)

    # Check metrics
    summary = metrics.get_summary()
    fb = summary["feedback"]

    assert fb["true_positives"] == 1
    assert fb["false_positives"] == 1
    assert fb["precision"] == 0.5
    assert fb["fpr"] == 1.0  # FP / (FP + TN) = 1 / (1 + 0)


def test_feedback_service_ignores_non_classification_feedback(temp_store_path):
    """Test that ADJUST_RISK and IGNORE feedback don't affect classification metrics."""
    metrics = MetricsCollector()
    metrics.reset()

    store = FeedbackStore(storage_path=temp_store_path)
    service = FeedbackService(store=store, metrics_collector=metrics)

    # Add ADJUST_RISK feedback (should NOT be tracked in metrics)
    req = FeedbackRequest(
        check_id="TAINT_FLOW",
        metadata={"source": "input", "sink": "print"},
        feedback_type=FeedbackType.ADJUST_RISK,
        adjusted_score=50.0,
    )
    service.add_feedback(req)

    summary = metrics.get_summary()
    fb = summary["feedback"]

    # Metrics should remain 0
    assert fb["true_positives"] == 0
    assert fb["false_positives"] == 0
    assert fb["precision"] == 0.0

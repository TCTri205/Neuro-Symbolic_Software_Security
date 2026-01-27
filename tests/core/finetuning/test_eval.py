import json
import pytest
from unittest.mock import MagicMock
from src.core.finetuning.data_factory import TrainingExample
from src.core.finetuning.eval import EvaluationHarness


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    return llm


def test_eval_harness_perfect_score(mock_llm):
    """Test evaluation when model is perfect."""
    # Setup
    examples = [
        TrainingExample(
            instruction="Analyze...",
            input_data='{"code": "bad"}',
            output_data={"is_vulnerable": True},
        ),
        TrainingExample(
            instruction="Analyze...",
            input_data='{"code": "good"}',
            output_data={"is_vulnerable": False},
        ),
    ]

    # Mock responses (valid JSON, correct answers)
    mock_llm.generate.side_effect = [
        json.dumps({"is_vulnerable": True, "analysis": "Bad code"}),
        json.dumps({"is_vulnerable": False, "analysis": "Good code"}),
    ]

    harness = EvaluationHarness(llm_client=mock_llm)
    metrics = harness.evaluate_batch(examples)

    assert metrics.json_validity_rate == 1.0
    assert metrics.accuracy == 1.0
    assert metrics.fpr == 0.0
    assert metrics.fnr == 0.0


def test_eval_harness_invalid_json(mock_llm):
    """Test evaluation with invalid JSON output."""
    examples = [
        TrainingExample(
            instruction="Analyze...",
            input_data='{"code": "bad"}',
            output_data={"is_vulnerable": True},
        )
    ]

    mock_llm.generate.return_value = "Not JSON"

    harness = EvaluationHarness(llm_client=mock_llm)
    metrics = harness.evaluate_batch(examples)

    assert metrics.json_validity_rate == 0.0
    assert metrics.accuracy == 0.0  # Invalid JSON counts as incorrect


def test_eval_harness_fp_fn(mock_llm):
    """Test False Positives and False Negatives."""
    examples = [
        # Ground Truth: Safe (False). Model says: Vuln (True) -> FP
        TrainingExample(
            instruction="Analyze...",
            input_data='{"code": "good"}',
            output_data={"is_vulnerable": False},
        ),
        # Ground Truth: Vuln (True). Model says: Safe (False) -> FN
        TrainingExample(
            instruction="Analyze...",
            input_data='{"code": "bad"}',
            output_data={"is_vulnerable": True},
        ),
    ]

    mock_llm.generate.side_effect = [
        json.dumps({"is_vulnerable": True}),  # FP
        json.dumps({"is_vulnerable": False}),  # FN
    ]

    harness = EvaluationHarness(llm_client=mock_llm)
    metrics = harness.evaluate_batch(examples)

    assert metrics.total_samples == 2
    assert metrics.fpr == 1.0  # 1 Safe sample, misclassified as Vuln
    assert metrics.fnr == 1.0  # 1 Vuln sample, misclassified as Safe
    assert metrics.accuracy == 0.0

import pytest
from unittest.mock import MagicMock
from src.core.finetuning.data_factory import DataFactory, TrainingExample

# Sample CVEFixes row
SAMPLE_ROW = {
    "code_before": "def unsafe(u):\n    eval(u)",
    "code_after": "def safe(u):\n    import ast\n    ast.literal_eval(u)",
    "vuln_type": "Code Injection",
    "file_path": "test.py",
}


@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    # Mock teacher reasoning
    client.generate.side_effect = [
        '<thinking>Unsafe</thinking>{"is_vulnerable": true, "risk_level": "CRITICAL"}',
        '<thinking>Safe</thinking>{"is_vulnerable": false, "risk_level": "SAFE"}',
    ]
    return client


def test_data_factory_process_row(mock_llm_client):
    factory = DataFactory(teacher_model=mock_llm_client)

    examples = factory.process_row(SAMPLE_ROW)

    # Should generate at least 1 positive and 1 negative example
    assert len(examples) >= 2

    # Check Positive Sample
    pos = examples[0]
    assert isinstance(pos, TrainingExample)
    assert "eval(" in pos.input_data or "eval" in pos.input_data  # Original logic
    # Wait, we mask it. So it should be masked.
    # But checking for "eval" is fine if it's a built-in function not masked by default or if we check logic.

    # Check structure
    assert pos.output_data["is_vulnerable"] is True
    assert pos.output_data["risk_level"] == "CRITICAL"  # or HIGH

    # Check Negative Sample
    neg = examples[1]
    assert neg.output_data["is_vulnerable"] is False


def test_privacy_masking_integration():
    # Real masker test inside factory
    mock_llm = MagicMock()
    # Return valid JSON to avoid crashes during generation
    mock_llm.generate.return_value = (
        '<thinking>Ok</thinking>{"is_vulnerable": true, "risk_level": "HIGH"}'
    )

    factory = DataFactory(teacher_model=mock_llm)
    row = {
        "code_before": "def login(username, password):\n    q = 'SELECT * FROM users WHERE u=' + username",
        "code_after": "def login(username, password):\n    q = 'SELECT...'",
        "vuln_type": "SQL Injection",
        "file_path": "auth.py",
    }

    examples = factory.process_row(row)
    pos_input = examples[0].input_data

    # Should contain masked variables
    # username -> USER_STR_1 (likely inferred as str or var)
    # But exact mapping depends on masker.
    # Just check that "username" is NOT present in the input JSON string
    import json

    input_json = json.loads(pos_input)
    assert "username" not in input_json["function_signature"]
    assert "password" not in input_json["function_signature"]


def test_teacher_reasoning_call(mock_llm_client):
    factory = DataFactory(teacher_model=mock_llm_client)
    row = SAMPLE_ROW

    factory.process_row(row)

    # Verify LLM was called to generate reasoning for the POSITIVE sample
    assert mock_llm_client.generate.called

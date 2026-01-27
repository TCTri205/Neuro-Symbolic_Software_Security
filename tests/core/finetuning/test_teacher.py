import pytest
from unittest.mock import MagicMock
from src.core.finetuning.teacher import TeacherGenerator


@pytest.fixture
def mock_llm_client():
    return MagicMock()


def test_teacher_generate_success(mock_llm_client):
    # Setup
    mock_llm_client.generate.return_value = """<thinking>
The code has a SQL injection vulnerability because...
</thinking>
{
    "is_vulnerable": true,
    "analysis_summary": "SQLi detected",
    "risk_level": "CRITICAL"
}"""
    teacher = TeacherGenerator(llm_client=mock_llm_client)

    # Execute
    result = teacher.generate("def foo(x): ...", "SQL Injection", is_vulnerable=True)

    # Verify
    assert result["is_vulnerable"] is True
    assert result["analysis_summary"] == "SQLi detected"
    # Check that prompt contains key instructions
    call_args = mock_llm_client.generate.call_args[0][0]
    assert "Senior Security Engineer" in call_args
    assert "<thinking>" in call_args


def test_teacher_generate_invalid_json_retry(mock_llm_client):
    # Setup: First call returns garbage, second returns valid
    mock_llm_client.generate.side_effect = [
        "Just some text without JSON",
        """<thinking>Ok</thinking>{"is_vulnerable": false}""",
    ]
    teacher = TeacherGenerator(llm_client=mock_llm_client, max_retries=1)

    # Execute
    result = teacher.generate("def foo(x): ...", "XSS", is_vulnerable=False)

    # Verify
    assert result["is_vulnerable"] is False
    assert mock_llm_client.generate.call_count == 2


def test_teacher_generate_failure(mock_llm_client):
    # Setup: Always fails
    mock_llm_client.generate.return_value = "Invalid"
    teacher = TeacherGenerator(llm_client=mock_llm_client, max_retries=1)

    # Execute
    result = teacher.generate("...", "...", True)

    # Verify fallback
    assert result is None or result.get("analysis_summary") == "Generation Failed"

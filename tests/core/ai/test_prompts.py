import json
from unittest.mock import MagicMock
from src.core.ai.prompts import SecurityPromptBuilder


def test_build_analysis_prompt():
    builder = SecurityPromptBuilder()

    # Mock data
    block = MagicMock()
    block.scope = "test_func"
    block.security_findings = [{"check_id": "TEST", "line": 10}]
    # Mock statements for line calculation
    s1 = MagicMock()
    s1.lineno = 10
    s1.end_lineno = 11
    block.statements = [s1]

    snippet = "eval(x)"
    file_path = "test.py"
    ssa_context = {"defs": [{"name": "x", "version": 1}], "uses": [], "phi_nodes": []}

    prompt = builder.build_analysis_prompt(block, snippet, file_path, ssa_context)

    assert len(prompt) == 2
    assert prompt[0]["role"] == "system"
    assert builder.SYSTEM_ROLE in prompt[0]["content"]

    assert prompt[1]["role"] == "user"
    content = prompt[1]["content"]

    assert "File: test.py" in content
    assert "Scope: test_func" in content
    assert "Lines: 10-11" in content
    assert "eval(x)" in content
    assert "Definitions:" in content
    assert '"name": "x"' in content
    assert '"check_id": "TEST"' in content
    assert "Trace the data flow" in content

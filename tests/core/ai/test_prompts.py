from src.core.ai.prompts import SecurityPromptBuilder


def test_system_prompt_hardening():
    builder = SecurityPromptBuilder()
    system_prompt = builder.SYSTEM_ROLE
    assert "Do not suggest importing" in system_prompt
    assert "Return only valid JSON" in system_prompt

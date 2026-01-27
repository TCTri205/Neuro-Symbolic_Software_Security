from src.core.ai.policy import FallbackPolicy


def test_fallback_policy_chain():
    policy = FallbackPolicy("openai", ["gemini", "mock"])

    assert policy.get_current_provider() == "openai"

    assert policy.next_provider() == "gemini"
    assert policy.get_current_provider() == "gemini"

    assert policy.next_provider() == "mock"
    assert policy.get_current_provider() == "mock"

    assert policy.next_provider() is None
    assert policy.get_current_provider() == "mock"  # Stays at last


def test_fallback_reset():
    policy = FallbackPolicy("openai", ["gemini"])
    policy.next_provider()
    assert policy.get_current_provider() == "gemini"
    policy.reset()
    assert policy.get_current_provider() == "openai"

from src.core.ai.no_skip import NoSkipPolicy


def test_no_skip_policy_short_text():
    policy = NoSkipPolicy(max_chars=10)
    assert policy.apply("short") == "short"


def test_no_skip_policy_truncates():
    policy = NoSkipPolicy(max_chars=10, head_ratio=0.5)
    text = "0123456789ABCDEF"
    result = policy.apply(text)
    assert "<truncated>" in result
    assert result.startswith("01234")
    assert result.endswith("CDEF")

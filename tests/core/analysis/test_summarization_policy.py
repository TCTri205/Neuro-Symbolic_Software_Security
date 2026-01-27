from src.core.analysis.summarization_policy import SummarizationPolicy


def test_summarization_policy_analyze():
    policy = SummarizationPolicy(max_nodes=10, max_lines=10)
    assert policy.decide(node_count=5, line_count=5) == "analyze"


def test_summarization_policy_summarize():
    policy = SummarizationPolicy(max_nodes=10, max_lines=10)
    assert policy.decide(node_count=11, line_count=5) == "summarize"

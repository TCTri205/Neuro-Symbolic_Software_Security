import ast

from src.core.cfg.builder import CFGBuilder
from src.core.cfg.ssa.transformer import SSATransformer
from src.core.risk.ranker import RankerService
from src.core.taint.engine import (
    TaintConfiguration,
    TaintEngine,
    TaintSink,
    TaintSource,
)


def _analyze_flows(code: str, source_name: str, sink_name: str):
    tree = ast.parse(code)
    func_def = tree.body[0]

    builder = CFGBuilder()
    cfg = builder.build("foo", func_def)

    transformer = SSATransformer(cfg)
    transformer.analyze()

    config = TaintConfiguration(
        sources=[TaintSource(name=source_name)],
        sinks=[TaintSink(name=sink_name)],
    )

    engine = TaintEngine()
    return engine.analyze(cfg, transformer.ssa_map, config)


def test_ranker_scores_implicit_flows_higher():
    code = """
def foo():
    secret = source()
    if secret:
        x = 1
    else:
        x = 2
    sink(x)
    y = secret
    sink(y)
"""
    flows = _analyze_flows(code, "source", "sink")
    assert len(flows) >= 2

    ranker = RankerService()
    output = ranker.rank(flows)

    implicit_scores = [
        item.risk.risk_score for item in output.items if item.metadata["implicit"]
    ]
    explicit_scores = [
        item.risk.risk_score for item in output.items if not item.metadata["implicit"]
    ]
    assert implicit_scores
    assert explicit_scores
    assert max(implicit_scores) > max(explicit_scores)


def test_ranker_accounts_for_sensitivity_and_path_length():
    high_code = """
def foo():
    secret_token = secret_source()
    exec(secret_token)
"""
    low_code = """
def foo():
    user = user_input()
    tmp = user
    tmp2 = tmp
    print(tmp2)
"""

    flows = []
    flows.extend(_analyze_flows(high_code, "secret_source", "exec"))
    flows.extend(_analyze_flows(low_code, "user_input", "print"))
    assert len(flows) == 2

    ranker = RankerService()
    output = ranker.rank(flows)

    scores = {item.metadata["source"]: item.risk.risk_score for item in output.items}
    assert scores["secret_source"] > scores["user_input"]

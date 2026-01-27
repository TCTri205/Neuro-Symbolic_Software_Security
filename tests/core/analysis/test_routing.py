import ast

from src.core.cfg.builder import CFGBuilder
from src.core.cfg.ssa.transformer import SSATransformer
from src.core.risk.ranker import RankerService
from src.core.risk.routing import RoutingService
from src.core.risk.schema import RoutingTarget
from src.core.taint.engine import (
    TaintConfiguration,
    TaintEngine,
    TaintSink,
    TaintSource,
)


def _rank_code(code: str, source_name: str, sink_name: str):
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
    flows = engine.analyze(cfg, transformer.ssa_map, config)
    return RankerService().rank(flows)


def test_routing_sends_high_risk_to_llm():
    code = """
def foo():
    secret_token = secret_source()
    exec(secret_token)
"""
    ranked = _rank_code(code, "secret_source", "exec")
    routing = RoutingService().route(ranked)

    assert routing.overall is not None
    assert routing.overall.target == RoutingTarget.LLM


def test_routing_sends_low_risk_to_rules():
    code = """
def foo():
    user = user_input()
    tmp = user
    print(tmp)
"""
    ranked = _rank_code(code, "user_input", "print")
    routing = RoutingService().route(ranked)

    assert routing.overall is not None
    assert routing.overall.target == RoutingTarget.RULES

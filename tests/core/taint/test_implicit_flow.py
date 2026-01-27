import ast

from src.core.cfg.builder import CFGBuilder
from src.core.cfg.ssa.transformer import SSATransformer
from src.core.taint.engine import (
    TaintConfiguration,
    TaintEngine,
    TaintSink,
    TaintSource,
)


def test_implicit_flow_if_branch_taints_assignments():
    code = """
def foo():
    secret = source()
    if secret:
        x = 1
    else:
        x = 2
    sink(x)
"""
    tree = ast.parse(code)
    func_def = tree.body[0]

    builder = CFGBuilder()
    cfg = builder.build("foo", func_def)

    transformer = SSATransformer(cfg)
    transformer.analyze()

    config = TaintConfiguration(
        sources=[TaintSource(name="source")], sinks=[TaintSink(name="sink")]
    )

    engine = TaintEngine()
    results = engine.analyze(cfg, transformer.ssa_map, config)

    assert len(results) == 2
    assert {flow.source for flow in results} == {"source"}
    assert {flow.sink for flow in results} == {"sink"}

    paths = [tuple(flow.path) for flow in results]
    assert len(set(paths)) == 2
    assert all(path[-1].startswith("x_") for path in paths)

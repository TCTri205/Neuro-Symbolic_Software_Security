import ast
from src.core.taint.engine import (
    TaintEngine,
    TaintConfiguration,
    TaintSource,
    TaintSink,
)
from src.core.cfg.models import ControlFlowGraph, BasicBlock


# Mocking the CFG and SSA structures
class MockSSATransformer:
    def __init__(self, ssa_map):
        self.ssa_map = ssa_map


def create_mock_cfg_and_ssa():
    """
    Simulates:
      x = source()  # Block 1
      y = x         # Block 1
      sink(y)       # Block 1
    """
    cfg = ControlFlowGraph("test_graph")
    block = BasicBlock(id=1)

    # 1. x = source()
    source_call = ast.Call(
        func=ast.Name(id="source", ctx=ast.Load()), args=[], keywords=[]
    )
    assign_x = ast.Assign(
        targets=[ast.Name(id="x", ctx=ast.Store())], value=source_call
    )
    block.add_statement(assign_x)

    # 2. y = x
    # Note: x is Load here
    read_x = ast.Name(id="x", ctx=ast.Load())
    assign_y = ast.Assign(targets=[ast.Name(id="y", ctx=ast.Store())], value=read_x)
    block.add_statement(assign_y)

    # 3. sink(y)
    read_y = ast.Name(id="y", ctx=ast.Load())
    sink_call = ast.Call(
        func=ast.Name(id="sink", ctx=ast.Load()), args=[read_y], keywords=[]
    )
    expr_sink = ast.Expr(value=sink_call)
    block.add_statement(expr_sink)

    cfg.add_block(block)
    cfg.entry_block = block

    # SSA Map construction
    # We map specific AST node instances to SSA versions
    ssa_map = {
        # x = source() -> x_1 defined
        assign_x.targets[0]: "x_1",
        # y = x -> use x_1, define y_1
        read_x: "x_1",
        assign_y.targets[0]: "y_1",
        # sink(y) -> use y_1
        read_y: "y_1",
    }

    return cfg, ssa_map


def create_mock_cfg_with_sanitizer():
    """
    Simulates:
      x = source()
      y = html.escape(x)
      sink(y)
    """
    cfg = ControlFlowGraph("test_graph")
    block = BasicBlock(id=1)

    source_call = ast.Call(
        func=ast.Name(id="source", ctx=ast.Load()), args=[], keywords=[]
    )
    assign_x = ast.Assign(
        targets=[ast.Name(id="x", ctx=ast.Store())], value=source_call
    )
    block.add_statement(assign_x)

    read_x = ast.Name(id="x", ctx=ast.Load())
    sanitizer_call = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="html", ctx=ast.Load()),
            attr="escape",
            ctx=ast.Load(),
        ),
        args=[read_x],
        keywords=[],
    )
    assign_y = ast.Assign(
        targets=[ast.Name(id="y", ctx=ast.Store())], value=sanitizer_call
    )
    block.add_statement(assign_y)

    read_y = ast.Name(id="y", ctx=ast.Load())
    sink_call = ast.Call(
        func=ast.Name(id="sink", ctx=ast.Load()), args=[read_y], keywords=[]
    )
    expr_sink = ast.Expr(value=sink_call)
    block.add_statement(expr_sink)

    cfg.add_block(block)
    cfg.entry_block = block

    ssa_map = {
        assign_x.targets[0]: "x_1",
        read_x: "x_1",
        assign_y.targets[0]: "y_1",
        read_y: "y_1",
    }

    return cfg, ssa_map


def test_simple_taint_propagation():
    cfg, ssa_map = create_mock_cfg_and_ssa()

    config = TaintConfiguration(
        sources=[TaintSource(name="source")], sinks=[TaintSink(name="sink")]
    )

    engine = TaintEngine()
    results = engine.analyze(cfg, ssa_map, config)

    assert len(results) == 1
    flow = results[0]
    assert flow.source == "source"
    assert flow.sink == "sink"
    # Optional: Check path length or details
    # Path should conceptually be: source() -> x_1 -> y_1 -> sink()


def test_sanitizer_blocks_flow():
    cfg, ssa_map = create_mock_cfg_with_sanitizer()

    config = TaintConfiguration(
        sources=[TaintSource(name="source")],
        sinks=[TaintSink(name="sink")],
        sanitizers=["html.escape"],
    )

    engine = TaintEngine()
    results = engine.analyze(cfg, ssa_map, config)

    assert results == []

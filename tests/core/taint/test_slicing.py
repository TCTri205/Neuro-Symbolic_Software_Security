import ast

from src.core.cfg.models import BasicBlock, ControlFlowGraph, PhiNode
from src.core.taint.engine import (
    TaintConfiguration,
    TaintEngine,
    TaintSink,
    TaintSource,
)


def create_mock_cfg_with_phi():
    """
    Simulates:
      x = source()
      if cond:
          y = x
      else:
          y = x
      y = phi(y_1, y_2)
      z = y
      sink(z)
    """
    cfg = ControlFlowGraph("phi_graph")

    block_entry = BasicBlock(id=1)
    block_then = BasicBlock(id=2)
    block_else = BasicBlock(id=3)
    block_join = BasicBlock(id=4)

    source_call = ast.Call(
        func=ast.Name(id="source", ctx=ast.Load()), args=[], keywords=[]
    )
    assign_x = ast.Assign(
        targets=[ast.Name(id="x", ctx=ast.Store())], value=source_call
    )
    block_entry.add_statement(assign_x)

    read_x_then = ast.Name(id="x", ctx=ast.Load())
    assign_y_then = ast.Assign(
        targets=[ast.Name(id="y", ctx=ast.Store())], value=read_x_then
    )
    block_then.add_statement(assign_y_then)

    read_x_else = ast.Name(id="x", ctx=ast.Load())
    assign_y_else = ast.Assign(
        targets=[ast.Name(id="y", ctx=ast.Store())], value=read_x_else
    )
    block_else.add_statement(assign_y_else)

    phi = PhiNode(var_name="y", result="y_3", operands={2: "y_1", 3: "y_2"})
    block_join.add_phi(phi)

    read_y_phi = ast.Name(id="y", ctx=ast.Load())
    assign_z = ast.Assign(targets=[ast.Name(id="z", ctx=ast.Store())], value=read_y_phi)
    block_join.add_statement(assign_z)

    read_z = ast.Name(id="z", ctx=ast.Load())
    sink_call = ast.Call(
        func=ast.Name(id="sink", ctx=ast.Load()), args=[read_z], keywords=[]
    )
    block_join.add_statement(ast.Expr(value=sink_call))

    for block in [block_entry, block_then, block_else, block_join]:
        cfg.add_block(block)

    cfg.add_edge(1, 2, label="true")
    cfg.add_edge(1, 3, label="false")
    cfg.add_edge(2, 4)
    cfg.add_edge(3, 4)
    cfg.entry_block = block_entry

    ssa_map = {
        assign_x.targets[0]: "x_1",
        read_x_then: "x_1",
        assign_y_then.targets[0]: "y_1",
        read_x_else: "x_1",
        assign_y_else.targets[0]: "y_2",
        read_y_phi: "y_3",
        assign_z.targets[0]: "z_1",
        read_z: "z_1",
    }

    return cfg, ssa_map


def test_backward_slice_includes_phi_branches():
    cfg, ssa_map = create_mock_cfg_with_phi()

    config = TaintConfiguration(
        sources=[TaintSource(name="source")], sinks=[TaintSink(name="sink")]
    )

    engine = TaintEngine()
    results = engine.analyze(cfg, ssa_map, config)

    assert len(results) == 2
    paths = [flow.path for flow in results]

    assert all(path[0] == "x_1" for path in paths)
    assert all(path[-1] == "z_1" for path in paths)
    assert all("y_3" in path for path in paths)
    assert any("y_1" in path for path in paths)
    assert any("y_2" in path for path in paths)

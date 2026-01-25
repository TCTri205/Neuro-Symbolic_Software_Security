import ast
import pytest
from src.core.cfg.builder import CFGBuilder
from src.core.cfg.ssa.transformer import SSATransformer

def test_ssa_simple_assign():
    code = """
def foo(a):
    x = 1
    y = x + a
    return y
"""
    tree = ast.parse(code)
    func_def = tree.body[0]
    
    builder = CFGBuilder()
    cfg = builder.build("foo", func_def)
    
    transformer = SSATransformer(cfg)
    transformer.analyze()
    
    # Check if x is versioned
    # We can check the ssa_map
    assert len(transformer.ssa_map) > 0
    
    # Find the assignment node for x
    # AST structure: Assign(targets=[Name(id='x')], value=Constant(value=1))
    # We need to find this node in the statements
    assign_stmt = None
    for block in cfg._blocks.values():
        for stmt in block.statements:
            if isinstance(stmt, ast.Assign) and stmt.targets[0].id == 'x':
                assign_stmt = stmt
                break
    
    assert assign_stmt is not None
    target_node = assign_stmt.targets[0]
    assert target_node in transformer.ssa_map
    assert transformer.ssa_map[target_node].startswith("x_")

def test_ssa_phi_insertion():
    code = """
def foo(cond):
    if cond:
        x = 1
    else:
        x = 2
    return x
"""
    tree = ast.parse(code)
    func_def = tree.body[0]
    
    builder = CFGBuilder()
    cfg = builder.build("foo", func_def)
    
    transformer = SSATransformer(cfg)
    transformer.analyze()
    
    # Check for Phi node for x
    # It should be in the join block (after if/else)
    # Join block usually has the 'return x'
    
    phi_found = False
    for block in cfg._blocks.values():
        for phi in block.phi_nodes:
            if phi.var_name == 'x':
                phi_found = True
                assert len(phi.operands) >= 2
    
    assert phi_found

def test_ssa_loop_phi():
    code = """
def foo(n):
    x = 0
    while n > 0:
        x = x + n
        n = n - 1
    return x
"""
    tree = ast.parse(code)
    func_def = tree.body[0]
    
    builder = CFGBuilder()
    cfg = builder.build("foo", func_def)
    
    transformer = SSATransformer(cfg)
    transformer.analyze()
    
    # x and n should have Phi nodes in the loop header
    phis = set()
    for block in cfg._blocks.values():
        for phi in block.phi_nodes:
            phis.add(phi.var_name)
            
    assert 'x' in phis
    assert 'n' in phis

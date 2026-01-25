import ast
from src.core.cfg.builder import CFGBuilder

def build_cfg_from_code(code: str):
    tree = ast.parse(code)
    builder = CFGBuilder()
    return builder.build("test", tree)

def test_linear_flow():
    code = """
x = 1
y = 2
z = x + y
    """
    cfg = build_cfg_from_code(code)
    # Expect: 1 block (Entry/Main) containing 3 statements.
    # Actually, my builder creates Entry, visits module body.
    # Module body visits Assigns.
    
    # Implementation detail: Entry block is created. Statements added to it.
    assert len(cfg.nodes) >= 1
    # Check if we have the statements
    entry = cfg.get_block(cfg.entry_block.id)
    assert len(entry.statements) == 3

def test_if_flow():
    code = """
if x > 0:
    y = 1
else:
    y = 2
z = y
    """
    cfg = build_cfg_from_code(code)
    # Structure:
    # 1. Entry (contains 'if test') -> split
    # 2. Then (y=1)
    # 3. Else (y=2)
    # 4. Join (z=y)
    
    # We expect at least 4 blocks.
    assert len(cfg.nodes) >= 4
    
    # Check edges
    # Entry -> Then (True)
    # Entry -> Else (False)
    # Then -> Join
    # Else -> Join
    
    # We can check degrees
    g = cfg.graph
    entry_id = cfg.entry_block.id
    assert g.out_degree(entry_id) == 2

def test_while_flow():
    code = """
while x < 10:
    x = x + 1
print(x)
    """
    cfg = build_cfg_from_code(code)
    # Structure:
    # 1. Entry -> Header
    # 2. Header (test) -> Body (True) / Exit (False)
    # 3. Body -> Header
    # 4. Exit
    
    assert len(cfg.nodes) >= 4
    
    # Check for cycle (back edge)
    cycles = list(import_nx().simple_cycles(cfg.graph))
    assert len(cycles) > 0

def import_nx():
    import networkx as nx
    return nx

def test_async_flow():
    code = """
async def foo():
    async for x in iter:
        await process(x)
"""
    # Note: ast.parse works fine with async syntax in Py3.
    tree = ast.parse(code)
    builder = CFGBuilder()
    cfg = builder.build("test_async", tree)
    
    # Check for loop cycle from async for
    import networkx as nx
    cycles = list(nx.simple_cycles(cfg.graph))
    assert len(cycles) > 0
    
    # Check for await expression
    found_await = False
    for block in cfg._blocks.values():
        for stmt in block.statements:
            # Depending on python version, await might be Expr(value=Await(...))
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Await):
                found_await = True
    assert found_await

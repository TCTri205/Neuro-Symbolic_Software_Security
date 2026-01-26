import ast
from src.core.cfg.builder import CFGBuilder


def test_async_await_splitting():
    code = """
async def my_func():
    x = 1
    y = await some_call()
    z = 2
"""
    tree = ast.parse(code)
    builder = CFGBuilder()
    cfg = builder.build("test_module", tree)

    blocks = [b for b in cfg._blocks.values() if b.scope == "my_func"]
    blocks.sort(key=lambda b: b.id)

    # We expect:
    # 1. Entry block
    # 2. x=1
    # 3. y=await...
    # 4. z=2
    # Plus potentially a post-def block if the structure implies it, but inside the function scope...
    # Actually, the CFGBuilder creates:
    # - Function Entry Block
    # - Then visits body.

    # Block 1 (Function Entry) might be empty if no args, or contain args.
    # Block 2: x=1
    # Block 3: y=await...
    # Block 4: z=2

    # Let's map statements to blocks
    block_map = {}
    for b in blocks:
        for stmt in b.statements:
            if isinstance(stmt, ast.Assign):
                target = stmt.targets[0].id
                block_map[target] = b

    assert "x" in block_map
    assert "y" in block_map
    assert "z" in block_map

    b_x = block_map["x"]
    b_y = block_map["y"]
    b_z = block_map["z"]

    # Verify separation
    assert b_x.id != b_y.id
    assert b_y.id != b_z.id

    # Verify edges
    # b_x -> b_y
    assert cfg.graph.has_edge(b_x.id, b_y.id)
    # b_y -> b_z with "Resume" label
    edge_data = cfg.graph.get_edge_data(b_y.id, b_z.id)
    assert edge_data is not None
    assert edge_data.get("label") == "Resume"


def test_async_for_edges():
    code = """
async def loop():
    async for i in data:
        pass
"""
    tree = ast.parse(code)
    builder = CFGBuilder()
    cfg = builder.build("loop_test", tree)

    # Find the header block of the loop
    # It contains 'i' (target) and 'data' (iter)
    blocks = [b for b in cfg._blocks.values() if b.scope == "loop"]
    header = None
    for b in blocks:
        stmts = [ast.dump(s) for s in b.statements]
        # Look for Name(id='i', ctx=Store())
        if any("id='i'" in s and "Store" in s for s in stmts):
            header = b
            break

    assert header is not None

    # Check outgoing edges
    out_edges = list(cfg.graph.out_edges(header.id, data=True))
    labels = [d.get("label") for _, _, d in out_edges]

    # Expect AsyncNext and AsyncStop (or equivalent)
    assert "AsyncNext" in labels
    assert "AsyncStop" in labels


def test_async_with_edges():
    code = """
async def context():
    async with lock:
        pass
"""
    tree = ast.parse(code)
    builder = CFGBuilder()
    cfg = builder.build("ctx_test", tree)

    # Find block with 'lock' (Load)
    blocks = [b for b in cfg._blocks.values() if b.scope == "context"]
    pre_block = None
    for b in blocks:
        stmts = [ast.dump(s) for s in b.statements]
        if any("id='lock'" in s and "Load" in s for s in stmts):
            pre_block = b
            break

    assert pre_block is not None

    # Check edge to body
    out_edges = list(cfg.graph.out_edges(pre_block.id, data=True))
    # Should have one edge to body with AsyncEnter
    assert len(out_edges) == 1
    assert out_edges[0][2].get("label") == "AsyncEnter"

    # The body block flows into... where?
    # Logic needs to handle AsyncExit too if possible, or just normal flow.
    # Current implementation visits body, then continues.


def test_async_with_as_var():
    code = """
async def context_var():
    async with lock as l:
        pass
"""
    tree = ast.parse(code)
    builder = CFGBuilder()
    cfg = builder.build("ctx_var_test", tree)

    blocks = [b for b in cfg._blocks.values() if b.scope == "context_var"]
    pre_block = None
    for b in blocks:
        stmts = [ast.dump(s) for s in b.statements]
        # Look for Name(id='l', ctx=Store()) which is the optional var
        if any("id='l'" in s and "Store" in s for s in stmts):
            pre_block = b
            break

    assert pre_block is not None
    # Verify it flows to body with AsyncEnter
    out_edges = list(cfg.graph.out_edges(pre_block.id, data=True))
    assert len(out_edges) == 1
    assert out_edges[0][2].get("label") == "AsyncEnter"


def test_async_func_args():
    code = """
async def func_with_args(a, b):
    pass
"""
    tree = ast.parse(code)
    builder = CFGBuilder()
    cfg = builder.build("func_args_test", tree)

    blocks = [b for b in cfg._blocks.values() if b.scope == "func_with_args"]
    # Sort by ID to find entry
    blocks.sort(key=lambda b: b.id)
    entry = blocks[0]

    stmts = [ast.dump(s) for s in entry.statements]
    print(f"Entry block stmts: {stmts}")
    # Should contain arguments a and b
    # Note: arg in ast is 'arg', not 'Name'. ast.dump(arg) looks like "arg(arg='a', annotation=None, ...)"
    assert any("arg='a'" in s for s in stmts)
    assert any("arg='b'" in s for s in stmts)


def test_async_func_as_root():
    code = """
async def root_func():
    pass
"""
    tree = ast.parse(code)
    func_node = tree.body[0]
    builder = CFGBuilder()
    cfg = builder.build("root_test", func_node)

    # Check if entry edge exists from implicit entry to function entry
    # When building with FunctionDef as root, builder creates an entry_block,
    # then visits the function.
    # The visit_AsyncFunctionDef should link outer (entry_block) to func_entry.

    # cfg.entry_block is the global entry.
    # We expect an edge from cfg.entry_block.id to the function's entry block.

    blocks = [b for b in cfg._blocks.values() if b.scope == "root_func"]
    blocks.sort(key=lambda b: b.id)
    func_entry = blocks[0]

    assert cfg.graph.has_edge(cfg.entry_block.id, func_entry.id)
    edge_data = cfg.graph.get_edge_data(cfg.entry_block.id, func_entry.id)
    assert edge_data.get("label") == "Entry"

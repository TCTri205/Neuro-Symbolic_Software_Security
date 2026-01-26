import ast
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
            if isinstance(stmt, ast.Assign) and stmt.targets[0].id == "x":
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
            if phi.var_name == "x":
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

    assert "x" in phis
    assert "n" in phis


def test_ssa_aug_assign():
    code = """
def foo():
    x = 1
    x += 2
    return x
"""
    tree = ast.parse(code)
    func_def = tree.body[0]

    builder = CFGBuilder()
    cfg = builder.build("foo", func_def)

    transformer = SSATransformer(cfg)
    transformer.analyze()

    # x = 1 -> x_1
    # x += 2 -> x_2 = x_1 + 2

    # Find the AugAssign node
    aug_assign = None
    for block in cfg._blocks.values():
        for stmt in block.statements:
            if isinstance(stmt, ast.AugAssign):
                aug_assign = stmt
                break

    assert aug_assign is not None

    # The target 'x' in 'x += 2' acts as both a use (read x_1) and a def (write x_2)
    # The current transformer implementation might map the target node to the NEW version.
    # Let's verify what we expect.
    # Usually, we want to know that 'x' in 'x+=2' refers to the new version x_2 for downstream,
    # but strictly speaking, it READS x_1.

    target_ver = transformer.ssa_map.get(aug_assign.target)
    assert target_ver is not None
    # We expect the mapping to point to the NEW version because that's what subsequent uses will see
    # However, we also need to know it USES the old version.
    # The transformer should handle this internally.

    # Let's verify we have at least two versions of x
    versions = set()
    for node, ver in transformer.ssa_map.items():
        if isinstance(node, ast.Name) and node.id == "x":
            versions.add(ver)

    assert len(versions) >= 2  # x_1 and x_2


def test_ssa_for_loop():
    code = """
def foo(items):
    s = 0
    for x in items:
        s = s + x
    return s
"""
    tree = ast.parse(code)
    func_def = tree.body[0]

    builder = CFGBuilder()
    cfg = builder.build("foo", func_def)

    transformer = SSATransformer(cfg)
    transformer.analyze()

    # 'x' in 'for x in items' is a definition.
    # It should effectively have a Phi node because it changes every iteration?
    # Or simply be treated as a definition in the loop header block.

    # 's' should have a Phi node (s_0 outside, s_updated inside).

    phis = set()
    for block in cfg._blocks.values():
        for phi in block.phi_nodes:
            phis.add(phi.var_name)

    assert "s" in phis

    # Verify 'x' is versioned
    x_defs = [
        ver
        for node, ver in transformer.ssa_map.items()
        if isinstance(node, ast.Name) and node.id == "x"
    ]
    assert len(x_defs) > 0


def test_ssa_tuple_unpacking():
    code = """
def foo():
    a, b = 1, 2
    return a + b
"""
    tree = ast.parse(code)
    func_def = tree.body[0]

    builder = CFGBuilder()
    cfg = builder.build("foo", func_def)

    transformer = SSATransformer(cfg)
    transformer.analyze()

    # Find a and b assignments
    vers = set(transformer.ssa_map.values())
    found_a = any(v.startswith("a_") for v in vers)
    found_b = any(v.startswith("b_") for v in vers)

    assert found_a
    assert found_b


def test_ssa_definition_tracking():
    """
    Test that we can track a version back to its definition node.
    This is critical for taint tracking.
    """
    code = """
def foo():
    query = "SELECT * FROM users"
    execute(query)
"""
    tree = ast.parse(code)
    func_def = tree.body[0]

    builder = CFGBuilder()
    cfg = builder.build("foo", func_def)

    transformer = SSATransformer(cfg)
    transformer.analyze()

    # 1. Find the usage of 'query' in 'execute(query)'
    call_stmt = None
    for block in cfg._blocks.values():
        for stmt in block.statements:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call_stmt = stmt.value
                break

    assert call_stmt is not None
    arg_node = call_stmt.args[0]  # 'query'
    assert isinstance(arg_node, ast.Name)
    assert arg_node.id == "query"

    # 2. Get the version
    ver = transformer.ssa_map.get(arg_node)
    assert ver is not None

    # 3. Resolve definition
    # We expect the transformer to have a map for this
    # Let's call it 'def_map' or 'version_defs'

    assert hasattr(transformer, "version_defs")

    # version_defs returns (def_node, stmt) tuple
    result = transformer.version_defs.get(ver)
    assert result is not None
    assert isinstance(result, tuple)
    def_node, stmt = result

    # It should be the target Name node in the assignment or similar
    # In 'query = "SELECT..."', the definition source is the 'query' Name node in Assign.targets

    assert isinstance(def_node, ast.Name)
    assert def_node.id == "query"

    # And we can now check the statement too
    assert isinstance(stmt, ast.Assign)
    # And the value should be "SELECT..."
    assert isinstance(stmt.value, ast.Constant)
    assert stmt.value.value == "SELECT * FROM users"

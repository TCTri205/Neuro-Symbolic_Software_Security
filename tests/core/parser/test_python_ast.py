from src.core.parser import PythonAstParser


def _kinds(graph):
    return {node.kind for node in graph.nodes}


def test_parse_import_try_with_for():
    source = """
import os
from math import sqrt as root

def work(items, path):
    for item in items:
        pass
    try:
        with open(path) as f:
            data = f.read()
    except OSError:
        data = ""
    return data
"""
    parser = PythonAstParser(source, "example.py")
    graph = parser.parse()

    kinds = _kinds(graph)
    assert "Import" in kinds
    assert "For" in kinds
    assert "Try" in kinds
    assert "With" in kinds

    try_nodes = [n for n in graph.nodes if n.kind == "Try"]
    assert len(try_nodes) == 1
    try_id = try_nodes[0].id
    exception_edges = [e for e in graph.edges if e.type == "exception"]
    assert exception_edges
    for edge in exception_edges:
        assert edge.guard_id == try_id


def test_parse_await_and_yield():
    source = """
async def fetch():
    await call()

def gen():
    yield 1
"""
    parser = PythonAstParser(source, "example.py")
    graph = parser.parse()

    kinds = _kinds(graph)
    assert "Await" in kinds
    assert "Yield" in kinds


def test_parse_break_continue_raise_and_symbols():
    source = """
def loop(values):
    total = 0
    for item in values:
        if item == 0:
            continue
        if item < 0:
            break
        total = total + item
    raise ValueError("bad")
    return total
"""
    parser = PythonAstParser(source, "example.py")
    graph = parser.parse()

    kinds = _kinds(graph)
    assert "Break" in kinds
    assert "Continue" in kinds
    assert "Raise" in kinds

    symbol_names = {s.name for s in graph.symbols}
    assert "values" in symbol_names
    assert "total" in symbol_names

    break_edges = [e for e in graph.edges if e.type == "break"]
    continue_edges = [e for e in graph.edges if e.type == "continue"]
    assert len(break_edges) == 1
    assert len(continue_edges) == 1

    total_symbol = next(s for s in graph.symbols if s.name == "total")
    assert len(total_symbol.defs) >= 2
    assert len(total_symbol.uses) >= 1


def test_parse_annassign_augassign_global():
    source = """
count: int = 0

def inc():
    global count
    count += 1
"""
    parser = PythonAstParser(source, "example.py")
    graph = parser.parse()

    assign_nodes = [n for n in graph.nodes if n.kind == "Assign"]
    ann_assign = next((n for n in assign_nodes if "annotation" in n.attrs), None)
    aug_assign = next((n for n in assign_nodes if "op" in n.attrs), None)

    assert ann_assign is not None
    assert ann_assign.attrs["annotation"] == "int"
    assert aug_assign is not None
    assert aug_assign.attrs["op"] == "Add"

    count_symbol = next((s for s in graph.symbols if s.name == "count"), None)
    assert count_symbol is not None


def test_parse_class_lambda_and_literals():
    source = """
class Box:
    def __init__(self, value):
        self.value = value

def make():
    fn = lambda x: x + 1
    items = [1, 2]
    data = {"a": 1}
    ok = True and False
    neg = -1
    return fn(1)
"""
    parser = PythonAstParser(source, "example.py")
    graph = parser.parse()

    kinds = _kinds(graph)
    assert "Class" in kinds
    assert "Lambda" in kinds
    assert "BoolOp" in kinds
    assert "UnaryOp" in kinds
    assert "Literal" in kinds


def test_parse_comprehensions():
    source = """
def comp(values):
    squares = [x * x for x in values if x > 0]
    mapping = {x: x for x in values}
    gen = (x for x in values)
    return squares
"""
    parser = PythonAstParser(source, "example.py")
    graph = parser.parse()

    literal_nodes = [n for n in graph.nodes if n.kind == "Literal"]
    comp_nodes = [n for n in literal_nodes if "generators" in n.attrs]
    assert len(comp_nodes) >= 3


def test_parse_ifexp_namedexpr_match_and_comp_scope():
    source = """
def decide(x, items):
    y = x if x > 0 else -x
    if (n := x) > 0:
        pass
    match x:
        case 0:
            y = 0
        case _:
            y = 1
    vals = [i for i in items]
    return y
"""
    parser = PythonAstParser(source, "example.py")
    graph = parser.parse()

    kinds = _kinds(graph)
    assert "IfExp" in kinds
    assert "NamedExpr" in kinds
    assert "Match" in kinds

    comp_nodes = [
        n for n in graph.nodes if n.kind == "Literal" and "comp_scope" in n.attrs
    ]
    assert comp_nodes

    comp_scopes = {n.attrs.get("comp_scope") for n in comp_nodes}
    comp_scopes.discard(None)
    assert comp_scopes
    comp_vars = [
        s for s in graph.symbols if s.name == "i" and s.scope_id in comp_scopes
    ]
    assert comp_vars

    match_nodes = [n for n in graph.nodes if n.kind == "Match"]
    assert match_nodes
    cases = match_nodes[0].attrs.get("cases", [])
    assert cases


def test_match_binds_symbols():
    source = """
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

def pick(v):
    match v:
        case {"k": x}:
            return x
        case [a, b]:
            return a
        case {"k": x, **rest}:
            return x
        case [*tail]:
            return tail
        case Point(x=c, y=d):
            return c
        case [a, b] as seq:
            return seq
"""
    parser = PythonAstParser(source, "example.py")
    graph = parser.parse()

    match_node = next(n for n in graph.nodes if n.kind == "Match")
    cases = match_node.attrs.get("cases", [])
    binds = {name for case in cases for name in case.get("binds", [])}
    assert "x" in binds
    assert "a" in binds
    assert "b" in binds
    assert "rest" in binds
    assert "tail" in binds
    assert "c" in binds
    assert "d" in binds
    assert "seq" in binds

    bound_symbols = {s.name for s in graph.symbols}
    assert "x" in bound_symbols
    assert "a" in bound_symbols
    assert "b" in bound_symbols
    assert "rest" in bound_symbols
    assert "tail" in bound_symbols
    assert "c" in bound_symbols
    assert "d" in bound_symbols
    assert "seq" in bound_symbols


def test_symbol_defs_and_uses():
    source = """
def calc(x):
    y = x + 1
    return y
"""
    parser = PythonAstParser(source, "example.py")
    graph = parser.parse()

    x_symbol = next((s for s in graph.symbols if s.name == "x"), None)
    y_symbol = next((s for s in graph.symbols if s.name == "y"), None)

    assert x_symbol is not None
    assert x_symbol.kind == "param"
    assert len(x_symbol.defs) == 1
    assert len(x_symbol.uses) >= 1

    assert y_symbol is not None
    assert y_symbol.kind == "var"
    assert len(y_symbol.defs) == 1
    assert len(y_symbol.uses) >= 1

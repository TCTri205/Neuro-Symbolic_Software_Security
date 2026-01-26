import pytest
from src.core.parser.ir import IRSpan, extract_source_code
from src.core.parser.python_ast import PythonAstParser


def test_extract_source_code_basic():
    source = "x = 1\ny = 2\n"
    # x = 1 (line 1)
    span = IRSpan(file="test.py", start_line=1, start_col=0, end_line=1, end_col=5)
    assert extract_source_code(source, span) == "x = 1"


def test_extract_source_code_unicode():
    source = "x = '🔥'"
    # '🔥' is at col 4, end col 10 (3 chars + quotes, but byte offset)
    # ' (1) + 🔥 (4) + ' (1) = 6 bytes. 4 + 6 = 10.
    span = IRSpan(file="test.py", start_line=1, start_col=4, end_line=1, end_col=10)
    assert extract_source_code(source, span) == "'🔥'"


def test_extract_source_code_multiline():
    source = "x = '''\nfoo\n'''"
    # start line 1, col 4 ("'''")
    # end line 3, col 3 ("'''")
    span = IRSpan(file="test.py", start_line=1, start_col=4, end_line=3, end_col=3)
    assert extract_source_code(source, span) == "'''\nfoo\n'''"


def test_parser_source_mapping():
    code = """
def foo(x):
    return x + 1
"""
    parser = PythonAstParser(code, "test.py")
    graph = parser.parse()

    # Find Function node
    func_node = next(n for n in graph.nodes if n.kind == "Function")
    # foo(x) starts at line 2.
    # def foo(x): ...
    extracted = parser.get_source_segment(func_node.id)
    assert extracted.startswith("def foo(x):")
    assert "return x + 1" in extracted

    # Find Return node
    return_node = next(n for n in graph.nodes if n.kind == "Return")
    extracted_ret = parser.get_source_segment(return_node.id)
    assert extracted_ret == "return x + 1"


def test_parser_source_mapping_stripped_comments():
    from src.core.parser.preprocessing import strip_comments

    code = """
def foo(x):
    # comment
    return x + 1
"""
    stripped = strip_comments(code)
    # stripped should maintain layout
    # "    # comment\n" -> "             \n" (spaces)

    parser = PythonAstParser(stripped, "test.py")
    graph = parser.parse()

    return_node = next(n for n in graph.nodes if n.kind == "Return")
    # The return node should still be at the same location
    extracted = parser.get_source_segment(return_node.id)
    assert extracted == "return x + 1"

    # But if we ask for the whole function body, the comment line is spaces
    func_node = next(n for n in graph.nodes if n.kind == "Function")
    extracted_func = parser.get_source_segment(func_node.id)
    assert "return x + 1" in extracted_func
    assert "# comment" not in extracted_func
    assert "             " in extracted_func  # Assuming it replaces with spaces


def test_extract_source_invalid_span():
    source = "x = 1"
    span = IRSpan(file="test.py", start_line=-1, start_col=0, end_line=1, end_col=5)
    assert extract_source_code(source, span) == ""

    span = IRSpan(file="test.py", start_line=1, start_col=0, end_line=-1, end_col=5)
    assert extract_source_code(source, span) == ""

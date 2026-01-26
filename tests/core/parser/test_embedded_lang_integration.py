"""
Integration test for embedded language detection in the parser.

Validates that PythonAstParser correctly tags Literal nodes with embedded_lang.
"""

from src.core.parser.python_ast import PythonAstParser


def test_sql_detection_in_parser():
    """Test that SQL strings are tagged in the IR."""
    source = """
query = "SELECT * FROM users WHERE id = 1"
"""
    parser = PythonAstParser(source, "test.py")
    graph = parser.parse()

    # Find the Literal node
    literal_nodes = [
        n for n in graph.nodes if n.kind == "Literal" and "value" in n.attrs
    ]
    assert len(literal_nodes) > 0, "Should have at least one literal"

    sql_literal = next(
        (n for n in literal_nodes if "SELECT" in str(n.attrs.get("value", ""))), None
    )
    assert sql_literal is not None, "Should find SQL literal"
    assert sql_literal.attrs.get("embedded_lang") == "sql"
    assert sql_literal.attrs.get("embedded_lang_confidence", 0) >= 0.9


def test_shell_detection_in_parser():
    """Test that shell commands are tagged in the IR."""
    source = """
cmd = "ls -la | grep test"
"""
    parser = PythonAstParser(source, "test.py")
    graph = parser.parse()

    literal_nodes = [
        n for n in graph.nodes if n.kind == "Literal" and "value" in n.attrs
    ]
    shell_literal = next(
        (n for n in literal_nodes if "grep" in str(n.attrs.get("value", ""))), None
    )
    assert shell_literal is not None
    assert shell_literal.attrs.get("embedded_lang") == "shell"
    assert shell_literal.attrs.get("embedded_lang_confidence", 0) >= 0.8


def test_html_detection_in_parser():
    """Test that HTML strings are tagged in the IR."""
    source = """
html = "<div class='test'>Hello</div>"
"""
    parser = PythonAstParser(source, "test.py")
    graph = parser.parse()

    literal_nodes = [
        n for n in graph.nodes if n.kind == "Literal" and "value" in n.attrs
    ]
    html_literal = next(
        (n for n in literal_nodes if "<div" in str(n.attrs.get("value", ""))), None
    )
    assert html_literal is not None
    assert html_literal.attrs.get("embedded_lang") == "html"
    assert html_literal.attrs.get("embedded_lang_confidence", 0) >= 0.8


def test_json_detection_in_parser():
    """Test that JSON strings are tagged in the IR."""
    source = """
data = '{"name": "John", "age": 30}'
"""
    parser = PythonAstParser(source, "test.py")
    graph = parser.parse()

    literal_nodes = [
        n for n in graph.nodes if n.kind == "Literal" and "value" in n.attrs
    ]
    json_literal = next(
        (n for n in literal_nodes if "name" in str(n.attrs.get("value", ""))), None
    )
    assert json_literal is not None
    assert json_literal.attrs.get("embedded_lang") == "json"
    assert json_literal.attrs.get("embedded_lang_confidence", 0) >= 0.9


def test_no_detection_for_plain_strings():
    """Test that plain strings are not tagged."""
    source = """
message = "Hello, world!"
"""
    parser = PythonAstParser(source, "test.py")
    graph = parser.parse()

    literal_nodes = [
        n for n in graph.nodes if n.kind == "Literal" and "value" in n.attrs
    ]
    hello_literal = next(
        (n for n in literal_nodes if "Hello" in str(n.attrs.get("value", ""))), None
    )
    assert hello_literal is not None
    # Should not have embedded_lang attribute for plain text
    assert "embedded_lang" not in hello_literal.attrs


def test_real_world_vulnerable_sql():
    """Test detection of vulnerable SQL from benchmarks."""
    # Use a regular string instead of f-string for this test
    # (f-strings create JoinedStr nodes with multiple parts)
    source = """
def login(username, password):
    query = "SELECT * FROM users WHERE username = '{}' AND password = '{}'".format(username, password)
    return execute_query(query)
"""
    parser = PythonAstParser(source, "test.py")
    graph = parser.parse()

    literal_nodes = [
        n for n in graph.nodes if n.kind == "Literal" and "value" in n.attrs
    ]
    sql_literal = next(
        (n for n in literal_nodes if "SELECT" in str(n.attrs.get("value", ""))), None
    )
    assert sql_literal is not None
    assert sql_literal.attrs.get("embedded_lang") == "sql"
    # This is a security-critical detection
    assert sql_literal.attrs.get("embedded_lang_confidence", 0) >= 0.9


def test_non_string_literals_not_tagged():
    """Test that non-string literals (numbers, booleans) are not tagged."""
    source = """
number = 42
flag = True
pi = 3.14
"""
    parser = PythonAstParser(source, "test.py")
    graph = parser.parse()

    literal_nodes = [n for n in graph.nodes if n.kind == "Literal"]

    # All number/boolean literals should not have embedded_lang
    for node in literal_nodes:
        value_type = node.attrs.get("value_type")
        if value_type in ["int", "bool", "float"]:
            assert "embedded_lang" not in node.attrs


def test_multiline_sql():
    """Test detection of multi-line SQL strings."""
    source = '''
query = """
    SELECT u.name, o.total
    FROM users u
    JOIN orders o ON u.id = o.user_id
    WHERE o.total > 100
"""
'''
    parser = PythonAstParser(source, "test.py")
    graph = parser.parse()

    literal_nodes = [
        n for n in graph.nodes if n.kind == "Literal" and "value" in n.attrs
    ]
    sql_literal = next(
        (n for n in literal_nodes if "SELECT" in str(n.attrs.get("value", ""))), None
    )
    assert sql_literal is not None
    assert sql_literal.attrs.get("embedded_lang") == "sql"
    assert sql_literal.attrs.get("embedded_lang_confidence", 0) >= 0.85

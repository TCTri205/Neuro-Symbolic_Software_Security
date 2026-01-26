"""
Test decorator unrolling functionality for Flask/Django routes.
"""

from src.core.parser import PythonAstParser
from src.core.parser.decorator_unroll import (
    extract_decorator_metadata,
    is_route_decorator,
    get_route_info,
)
import ast


def test_extract_simple_route_decorator():
    """Test extraction of simple @app.route('/path') decorator."""
    source = """
@app.route('/users')
def get_users():
    pass
"""
    tree = ast.parse(source)
    func_node = tree.body[0]
    decorator = func_node.decorator_list[0]

    metadata = extract_decorator_metadata(decorator)

    assert metadata["type"] == "route"
    assert metadata["decorator_target"] == "app.route"
    assert metadata["route_path"] == "/users"
    assert metadata["methods"] is None


def test_extract_route_with_methods():
    """Test extraction of @app.route with methods parameter."""
    source = """
@app.route('/login', methods=['GET', 'POST'])
def login():
    pass
"""
    tree = ast.parse(source)
    func_node = tree.body[0]
    decorator = func_node.decorator_list[0]

    metadata = extract_decorator_metadata(decorator)

    assert metadata["type"] == "route"
    assert metadata["route_path"] == "/login"
    assert metadata["methods"] == ["GET", "POST"]


def test_extract_route_with_kwargs():
    """Test extraction of route decorator with additional kwargs."""
    source = """
@app.route('/api/items', methods=['GET'], strict_slashes=False)
def get_items():
    pass
"""
    tree = ast.parse(source)
    func_node = tree.body[0]
    decorator = func_node.decorator_list[0]

    metadata = extract_decorator_metadata(decorator)

    assert metadata["route_path"] == "/api/items"
    assert metadata["methods"] == ["GET"]
    assert "strict_slashes" in metadata["kwargs"]


def test_extract_simple_decorator():
    """Test extraction of simple decorators like @staticmethod."""
    source = """
@staticmethod
def helper():
    pass
"""
    tree = ast.parse(source)
    func_node = tree.body[0]
    decorator = func_node.decorator_list[0]

    metadata = extract_decorator_metadata(decorator)

    assert metadata["type"] == "staticmethod"
    assert metadata["decorator_target"] == "staticmethod"
    assert metadata["route_path"] is None


def test_is_route_decorator():
    """Test route decorator detection."""
    # Parse as a function to get the decorator properly
    route_source = """
@app.route('/test')
def test_func():
    pass
"""
    tree = ast.parse(route_source)
    route_decorator = tree.body[0].decorator_list[0]
    route_metadata = extract_decorator_metadata(route_decorator)
    assert is_route_decorator(route_metadata) is True

    simple_source = """
@staticmethod
def test_func():
    pass
"""
    tree = ast.parse(simple_source)
    simple_decorator = tree.body[0].decorator_list[0]
    simple_metadata = extract_decorator_metadata(simple_decorator)
    assert is_route_decorator(simple_metadata) is False


def test_get_route_info():
    """Test route information extraction."""
    source = """
@app.post('/api/data', methods=['POST', 'PUT'])
def handle_data():
    pass
"""
    tree = ast.parse(source)
    decorator = tree.body[0].decorator_list[0]
    metadata = extract_decorator_metadata(decorator)

    route_info = get_route_info(metadata)

    assert route_info is not None
    assert route_info["path"] == "/api/data"
    assert route_info["methods"] == ["POST", "PUT"]
    assert route_info["decorator_type"] == "post"


def test_parser_integration_flask():
    """Test full parser integration with Flask route decorators."""
    source = """
from flask import Flask, request

app = Flask(__name__)

@app.route('/download')
def download():
    filename = request.args.get('file')
    return send_file(filename)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    return username
"""
    parser = PythonAstParser(source, "test_flask.py")
    graph = parser.parse()

    # Find function nodes
    func_nodes = [n for n in graph.nodes if n.kind == "Function"]
    assert len(func_nodes) >= 2

    # Check download function
    download_node = next(n for n in func_nodes if n.attrs.get("name") == "download")
    assert "decorator_metadata" in download_node.attrs
    metadata_list = download_node.attrs["decorator_metadata"]
    assert len(metadata_list) == 1

    route_meta = metadata_list[0]
    assert route_meta["type"] == "route"
    assert route_meta["route_path"] == "/download"

    # Check login function
    login_node = next(n for n in func_nodes if n.attrs.get("name") == "login")
    login_metadata = login_node.attrs["decorator_metadata"][0]
    assert login_metadata["route_path"] == "/login"
    assert login_metadata["methods"] == ["POST"]


def test_parser_multiple_decorators():
    """Test parsing functions with multiple decorators."""
    source = """
@login_required
@app.route('/admin')
@require_role('admin')
def admin_panel():
    pass
"""
    parser = PythonAstParser(source, "test_multi_dec.py")
    graph = parser.parse()

    func_nodes = [n for n in graph.nodes if n.kind == "Function"]
    assert len(func_nodes) == 1

    func = func_nodes[0]
    metadata_list = func.attrs["decorator_metadata"]
    assert len(metadata_list) == 3

    # Find the route decorator
    route_decorators = [m for m in metadata_list if m["type"] == "route"]
    assert len(route_decorators) == 1
    assert route_decorators[0]["route_path"] == "/admin"


def test_django_style_decorator():
    """Test Django-style URL routing decorators."""
    source = """
from django.http import HttpResponse

@require_http_methods(["GET", "POST"])
def my_view(request):
    return HttpResponse("Hello")
"""
    parser = PythonAstParser(source, "test_django.py")
    graph = parser.parse()

    func_nodes = [n for n in graph.nodes if n.kind == "Function"]
    func = func_nodes[0]

    metadata = func.attrs["decorator_metadata"][0]
    assert metadata["type"] == "require_http_methods"
    # The argument is a list of HTTP methods
    assert len(metadata["kwargs"]) == 0  # No keyword args

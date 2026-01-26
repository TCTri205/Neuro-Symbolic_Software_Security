from unittest.mock import MagicMock
from src.core.context.loader import ProjectContext
from src.plugins.flask.plugin import FlaskPlugin


class TestFlaskPlugin:
    def test_detect_returns_true_for_flask_project(self):
        plugin = FlaskPlugin()
        context = MagicMock(spec=ProjectContext)
        context.pyproject = {"project": {"dependencies": ["Flask>=2.0", "requests"]}}
        assert plugin.detect(context) is True

    def test_detect_returns_false_for_non_flask_project(self):
        plugin = FlaskPlugin()
        context = MagicMock(spec=ProjectContext)
        context.pyproject = {"project": {"dependencies": ["django", "requests"]}}
        assert plugin.detect(context) is False

    def test_detect_handles_missing_dependencies(self):
        plugin = FlaskPlugin()
        context = MagicMock(spec=ProjectContext)
        context.pyproject = {}
        assert plugin.detect(context) is False

    def test_parse_routes(self, tmp_path):
        plugin = FlaskPlugin()

        # Create a sample Flask app in the temp directory
        app_file = tmp_path / "app.py"
        app_file.write_text(
            """
from flask import Flask, Blueprint

app = Flask(__name__)
bp = Blueprint('api', __name__)

@app.route("/")
def home():
    pass

@app.route("/user", methods=["POST", "PUT"])
def create_user():
    pass

@bp.route("/items")
def items():
    pass

@other.decorator
def not_a_route():
    pass
""",
            encoding="utf-8",
        )

        routes = plugin.parse_routes(str(tmp_path))

        assert len(routes) == 3

        # Verify /
        r1 = next(r for r in routes if r.path == "/")
        assert r1.method == "GET"
        assert r1.handler == "home"

        # Verify /user
        r2 = next(r for r in routes if r.path == "/user")
        assert "POST" in r2.method
        assert "PUT" in r2.method
        assert r2.handler == "create_user"

        # Verify /items
        r3 = next(r for r in routes if r.path == "/items")
        assert r3.method == "GET"
        assert r3.handler == "items"

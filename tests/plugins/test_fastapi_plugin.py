from unittest.mock import MagicMock
from src.core.context.loader import ProjectContext
from src.plugins.fastapi.plugin import FastAPIPlugin


class TestFastAPIPlugin:
    def test_detect_returns_true_for_fastapi_project(self):
        plugin = FastAPIPlugin()
        context = MagicMock(spec=ProjectContext)
        context.pyproject = {
            "project": {"dependencies": ["fastapi>=0.68.0", "uvicorn"]}
        }
        assert plugin.detect(context) is True

    def test_detect_returns_false_for_non_fastapi_project(self):
        plugin = FastAPIPlugin()
        context = MagicMock(spec=ProjectContext)
        context.pyproject = {"project": {"dependencies": ["django", "requests"]}}
        assert plugin.detect(context) is False

    def test_parse_routes(self, tmp_path):
        plugin = FastAPIPlugin()

        # Create a sample FastAPI app in the temp directory
        app_file = tmp_path / "main.py"
        app_file.write_text(
            """
from fastapi import FastAPI, APIRouter

app = FastAPI()
router = APIRouter()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/items/")
def create_item(item: dict):
    return item

@router.put("/users/{user_id}")
def update_user(user_id: int, item: dict):
    return {"user_id": user_id}

@app.api_route("/legacy", methods=["GET", "POST"])
def legacy_handler():
    pass

def not_a_route():
    pass
""",
            encoding="utf-8",
        )

        routes = plugin.parse_routes(str(tmp_path))

        assert len(routes) == 4

        # Verify /
        r1 = next(r for r in routes if r.path == "/")
        assert r1.method == "GET"
        assert r1.handler == "read_root"

        # Verify /items/
        r2 = next(r for r in routes if r.path == "/items/")
        assert r2.method == "POST"
        assert r2.handler == "create_item"

        # Verify /users/{user_id}
        r3 = next(r for r in routes if r.path == "/users/{user_id}")
        assert r3.method == "PUT"
        assert r3.handler == "update_user"

        # Verify /legacy
        r4 = next(r for r in routes if r.path == "/legacy")
        assert "GET" in r4.method
        assert "POST" in r4.method
        assert r4.handler == "legacy_handler"

import pytest
from abc import ABC
from dataclasses import dataclass
from typing import List
from src.core.context.loader import ProjectContext
from src.plugins.base import FrameworkPlugin, Route


@dataclass
class MockRoute(Route):
    pass


class ConcretePlugin(FrameworkPlugin):
    @property
    def name(self) -> str:
        return "mock_framework"

    def detect(self, context: ProjectContext) -> bool:
        return "mock_framework" in context.pyproject.get("tool", {})

    def parse_routes(self, project_path: str) -> List[Route]:
        return [Route(path="/api/test", method="GET", handler="test_handler")]


def test_plugin_interface():
    # Verify it's an abstract base class
    assert issubclass(FrameworkPlugin, ABC)

    # Create a mock context
    context = ProjectContext(pyproject={"tool": {"mock_framework": True}})

    # Instantiate concrete plugin
    plugin = ConcretePlugin()

    # Test detect
    assert plugin.detect(context) is True

    # Test parse_routes
    routes = plugin.parse_routes("/tmp")
    assert len(routes) == 1
    assert routes[0].path == "/api/test"
    assert routes[0].method == "GET"
    assert routes[0].handler == "test_handler"


def test_cannot_instantiate_interface():
    with pytest.raises(TypeError):
        FrameworkPlugin()

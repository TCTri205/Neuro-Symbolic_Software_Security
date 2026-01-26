from types import ModuleType
from src.core.context.loader import ProjectContext
from src.plugins.base import FrameworkPlugin
from src.plugins.loader import PluginLoader


class MockDjangoPlugin(FrameworkPlugin):
    @property
    def name(self) -> str:
        return "django"

    def detect(self, context: ProjectContext) -> bool:
        return True

    def parse_routes(self, project_path: str):
        return []


class MockFlaskPlugin(FrameworkPlugin):
    @property
    def name(self) -> str:
        return "flask"

    def detect(self, context: ProjectContext) -> bool:
        return False

    def parse_routes(self, project_path: str):
        return []


def test_get_active_plugins():
    loader = PluginLoader()
    # Manually register mock plugins for testing logic
    loader.register(MockDjangoPlugin())
    loader.register(MockFlaskPlugin())

    context = ProjectContext()  # Empty context

    active = loader.get_active_plugins(context)

    assert len(active) == 1
    assert active[0].name == "django"


def test_scan_module_for_plugins():
    loader = PluginLoader()

    # Create a mock module with a plugin class
    mock_mod = ModuleType("mock_plugin_module")
    mock_mod.MyPlugin = MockDjangoPlugin
    mock_mod.NotAPlugin = str  # Should be ignored

    loader._scan_module_for_plugins(mock_mod)

    assert len(loader.plugins) == 1
    assert loader.plugins[0].name == "django"


def test_scan_module_ignores_abstract_and_base():
    loader = PluginLoader()

    mock_mod = ModuleType("mock_abstract_module")
    mock_mod.Base = FrameworkPlugin  # Should be ignored (base)

    # Define an abstract subclass
    class AbstractPlugin(FrameworkPlugin):
        pass

    mock_mod.Abstract = AbstractPlugin  # Should be ignored (abstract)

    loader._scan_module_for_plugins(mock_mod)

    assert len(loader.plugins) == 0


def test_discover_graceful_failure():
    # Ensure discover doesn't crash if package is missing
    loader = PluginLoader()
    loader.discover("non.existent.package")
    assert len(loader.plugins) == 0

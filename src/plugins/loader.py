import importlib
import inspect
import pkgutil
import logging
from typing import List
from src.core.context.loader import ProjectContext
from src.plugins.base import FrameworkPlugin, PipelineEventPlugin

logger = logging.getLogger(__name__)


class PluginLoader:
    def __init__(self):
        self.plugins: List[FrameworkPlugin] = []

    def register(self, plugin: FrameworkPlugin):
        """Register a plugin instance."""
        self.plugins.append(plugin)

    def discover(self, package_name: str = "src.plugins"):
        """
        Dynamically discover and load plugins from a package.
        Iterates over submodules (e.g., django, flask) and looks for FrameworkPlugin subclasses.
        """
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            logger.warning(
                f"Could not import package {package_name} for plugin discovery."
            )
            return

        # Iterate over all submodules in the package
        if hasattr(package, "__path__"):
            for _, name, is_pkg in pkgutil.iter_modules(package.__path__):
                full_name = f"{package_name}.{name}"
                try:
                    module = importlib.import_module(full_name)
                    self._scan_module_for_plugins(module)
                except Exception as e:
                    logger.error(f"Failed to load plugin module {full_name}: {e}")

    def _scan_module_for_plugins(self, module):
        """Scan a module for FrameworkPlugin subclasses."""
        # DEBUG LOGGING
        print(f"Scanning module: {module.__name__}")
        for name, obj in inspect.getmembers(module):
            # print(f"  Member: {name}, Type: {type(obj)}")
            if inspect.isclass(obj):
                print(
                    f"    Is Class: {name}. Subclass: {issubclass(obj, FrameworkPlugin)}, Abstract: {inspect.isabstract(obj)}"
                )

        for name, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, FrameworkPlugin)
                and obj is not FrameworkPlugin
                and not inspect.isabstract(obj)
            ):
                # Instantiate and register
                # Check if already registered
                if not any(isinstance(p, obj) for p in self.plugins):
                    try:
                        instance = obj()
                        self.register(instance)
                        logger.info(f"Registered plugin: {instance.name}")
                    except Exception as e:
                        logger.error(f"Failed to instantiate plugin {name}: {e}")

    def get_active_plugins(self, context: ProjectContext) -> List[FrameworkPlugin]:
        """Return a list of plugins that detect the current context."""
        active = []
        for plugin in self.plugins:
            try:
                if plugin.detect(context):
                    active.append(plugin)
            except Exception as e:
                logger.error(f"Error in plugin {plugin.name}.detect(): {e}")
        return active


class PipelineEventPluginLoader:
    def __init__(self) -> None:
        self.plugins: List[PipelineEventPlugin] = []

    def register(self, plugin: PipelineEventPlugin) -> None:
        if any(isinstance(existing, plugin.__class__) for existing in self.plugins):
            return
        self.plugins.append(plugin)

    def discover(self, package_name: str = "src.plugins") -> None:
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            logger.warning(
                f"Could not import package {package_name} for plugin discovery."
            )
            return

        if hasattr(package, "__path__"):
            for _, name, _ in pkgutil.iter_modules(package.__path__):
                full_name = f"{package_name}.{name}"
                try:
                    module = importlib.import_module(full_name)
                    self._scan_module_for_plugins(module)
                except Exception as e:
                    logger.error(f"Failed to load plugin module {full_name}: {e}")

    def _scan_module_for_plugins(self, module) -> None:
        for _, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, PipelineEventPlugin)
                and obj is not PipelineEventPlugin
                and not inspect.isabstract(obj)
            ):
                if not any(isinstance(p, obj) for p in self.plugins):
                    try:
                        instance = obj()
                        self.register(instance)
                        logger.info(
                            "Registered pipeline event plugin: %s", instance.name
                        )
                    except Exception as e:
                        logger.error(f"Failed to instantiate plugin {obj}: {e}")

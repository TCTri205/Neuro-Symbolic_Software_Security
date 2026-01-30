from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.core.telemetry import get_logger


@dataclass
class PipelineContext:
    source_code: str
    file_path: str
    result: Any
    source_lines: List[str]
    stop_processing: bool = False

    def stop(self) -> None:
        self.stop_processing = True


class EventBus:
    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable[[PipelineContext], None]]] = {}

    def register(
        self, event_name: str, handler: Callable[[PipelineContext], None]
    ) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    def emit(self, event_name: str, context: PipelineContext) -> None:
        for handler in self._handlers.get(event_name, []):
            handler(context)


class PipelineEventRegistry:
    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable[[PipelineContext], None]]] = {}
        self._plugins_loaded = False

    def register(
        self, event_name: str, handler: Callable[[PipelineContext], None]
    ) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    def apply(self, event_bus: EventBus) -> None:
        for event_name, handlers in self._handlers.items():
            for handler in handlers:
                event_bus.register(event_name, handler)

    def plugins_loaded(self) -> bool:
        return self._plugins_loaded

    def mark_plugins_loaded(self) -> None:
        self._plugins_loaded = True


PIPELINE_STAGES = [
    "static_scan",
    "semgrep",
    "ir",
    "graph_build",
    "baseline",
    "ssa",
    "taint",
    "llm",
    "privacy",
]

PIPELINE_EVENTS = ["pre_analysis"]
for stage in PIPELINE_STAGES:
    PIPELINE_EVENTS.append(f"pre_{stage}")
    PIPELINE_EVENTS.append(stage)
    PIPELINE_EVENTS.append(f"post_{stage}")
PIPELINE_EVENTS.append("post_analysis")

_GLOBAL_REGISTRY = PipelineEventRegistry()


def get_pipeline_event_registry() -> PipelineEventRegistry:
    return _GLOBAL_REGISTRY


def register_pipeline_handler(
    event_name: str, handler: Callable[[PipelineContext], None]
) -> None:
    _GLOBAL_REGISTRY.register(event_name, handler)


def register_pipeline_plugins(
    registry: PipelineEventRegistry,
    package_name: str = "src.plugins",
    loader: Optional[object] = None,
) -> List[str]:
    if registry.plugins_loaded():
        return []

    logger = get_logger(__name__)
    if loader is None:
        try:
            from src.plugins.loader import PipelineEventPluginLoader

            loader = PipelineEventPluginLoader()
            loader.discover(package_name)
        except Exception as e:
            logger.error(f"Failed to load pipeline plugins: {e}")
            registry.mark_plugins_loaded()
            return []

    registered: List[str] = []
    for plugin in getattr(loader, "plugins", []):
        try:
            plugin.register(registry)
            registered.append(plugin.name)
        except Exception as e:
            logger.error(f"Failed to register pipeline plugin {plugin}: {e}")

    registry.mark_plugins_loaded()
    return registered


def register_plugin(
    plugin: Any,
    registry: Optional[PipelineEventRegistry] = None,
) -> None:
    """
    Register a plugin instance programmatically.

    This provides first-class plugin registration without requiring
    package discovery or core modifications.

    Args:
        plugin: Plugin instance implementing PipelineEventPlugin protocol
        registry: Target registry. If None, uses global registry.

    Example:
        >>> class MyPlugin(PipelineEventPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "my_plugin"
        ...     def register(self, registry):
        ...         registry.register("pre_analysis", my_handler)
        >>> register_plugin(MyPlugin())
    """
    if registry is None:
        registry = get_pipeline_event_registry()

    from src.plugins.base import PipelineEventPlugin

    if not isinstance(plugin, PipelineEventPlugin):
        raise TypeError(
            f"Plugin must implement PipelineEventPlugin, got {type(plugin)}"
        )

    plugin.register(registry)


def register_plugin_class(
    plugin_class: type,
    registry: Optional[PipelineEventRegistry] = None,
) -> None:
    """
    Register a plugin class (auto-instantiation).

    Args:
        plugin_class: Plugin class implementing PipelineEventPlugin protocol
        registry: Target registry. If None, uses global registry.

    Example:
        >>> register_plugin_class(MyPlugin)
    """
    if registry is None:
        registry = get_pipeline_event_registry()

    from src.plugins.base import PipelineEventPlugin

    if not issubclass(plugin_class, PipelineEventPlugin):
        raise TypeError(
            f"Plugin class must inherit from PipelineEventPlugin, got {plugin_class}"
        )

    instance = plugin_class()
    instance.register(registry)


def discover_plugins(
    package_name: str,
    registry: Optional[PipelineEventRegistry] = None,
) -> List[str]:
    """
    Discover and register plugins from a custom package.

    This enables external packages to provide plugins without
    modifying core code.

    Args:
        package_name: Python package name to scan (e.g., "my_plugins")
        registry: Target registry. If None, uses global registry.

    Returns:
        List of successfully registered plugin names

    Example:
        >>> discover_plugins("my_external_plugins")
        ['my_plugin_a', 'my_plugin_b']
    """
    if registry is None:
        registry = get_pipeline_event_registry()

    logger = get_logger(__name__)
    try:
        from src.plugins.loader import PipelineEventPluginLoader

        loader = PipelineEventPluginLoader()
        loader.discover(package_name)
    except Exception as e:
        logger.error(f"Failed to discover plugins from {package_name}: {e}")
        return []

    registered: List[str] = []
    for plugin in loader.plugins:
        try:
            plugin.register(registry)
            registered.append(plugin.name)
        except Exception as e:
            logger.error(f"Failed to register plugin {plugin}: {e}")

    return registered

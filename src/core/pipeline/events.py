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

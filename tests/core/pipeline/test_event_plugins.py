from types import ModuleType

from src.core.pipeline.events import (
    EventBus,
    PipelineContext,
    PipelineEventRegistry,
    register_pipeline_plugins,
)
from src.plugins.base import PipelineEventPlugin
from src.plugins.loader import PipelineEventPluginLoader


class MockPipelinePlugin(PipelineEventPlugin):
    @property
    def name(self) -> str:
        return "mock"

    def register(self, registry: PipelineEventRegistry) -> None:
        registry.register("pre_analysis", self._handler)

    def _handler(self, context: PipelineContext) -> None:
        count = context.result.get("handled", 0)
        context.result["handled"] = count + 1


def test_pipeline_event_plugin_loader_scan() -> None:
    loader = PipelineEventPluginLoader()
    mock_mod = ModuleType("mock_pipeline_plugin_module")
    mock_mod.MockPipelinePlugin = MockPipelinePlugin

    loader._scan_module_for_plugins(mock_mod)

    assert len(loader.plugins) == 1
    assert loader.plugins[0].name == "mock"


def test_register_pipeline_plugins_once() -> None:
    registry = PipelineEventRegistry()
    loader = PipelineEventPluginLoader()
    loader.register(MockPipelinePlugin())

    first = register_pipeline_plugins(registry, loader=loader)
    second = register_pipeline_plugins(registry, loader=loader)

    assert first == ["mock"]
    assert second == []

    event_bus = EventBus()
    registry.apply(event_bus)

    context = PipelineContext(
        source_code="",
        file_path="<memory>",
        result={},
        source_lines=[],
    )
    event_bus.emit("pre_analysis", context)

    assert context.result["handled"] == 1

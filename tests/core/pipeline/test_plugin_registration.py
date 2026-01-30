"""
Test suite for first-class plugin registration API.

This tests external plugins registering with the pipeline EventBus
without requiring modifications to core code.
"""

from src.core.pipeline.events import (
    EventBus,
    PipelineContext,
    PipelineEventRegistry,
    register_plugin,
    register_plugin_class,
    discover_plugins,
)
from src.plugins.base import PipelineEventPlugin


class ExternalPluginA(PipelineEventPlugin):
    """Mock external plugin to test programmatic registration."""

    @property
    def name(self) -> str:
        return "external_a"

    def register(self, registry: PipelineEventRegistry) -> None:
        registry.register("pre_analysis", self._on_pre_analysis)

    def _on_pre_analysis(self, context: PipelineContext) -> None:
        if not isinstance(context.result, dict):
            return
        context.result["external_a_called"] = True


class ExternalPluginB(PipelineEventPlugin):
    """Another external plugin."""

    @property
    def name(self) -> str:
        return "external_b"

    def register(self, registry: PipelineEventRegistry) -> None:
        registry.register("post_analysis", self._on_post_analysis)

    def _on_post_analysis(self, context: PipelineContext) -> None:
        if not isinstance(context.result, dict):
            return
        context.result["external_b_called"] = True


def test_register_plugin_instance() -> None:
    """Test registering a plugin instance programmatically."""
    registry = PipelineEventRegistry()
    plugin = ExternalPluginA()

    # Register the plugin instance
    register_plugin(plugin, registry=registry)

    # Apply to event bus and verify
    event_bus = EventBus()
    registry.apply(event_bus)

    context = PipelineContext(
        source_code="",
        file_path="<test>",
        result={},
        source_lines=[],
    )
    event_bus.emit("pre_analysis", context)

    assert context.result.get("external_a_called") is True


def test_register_plugin_class() -> None:
    """Test registering a plugin class (auto-instantiation)."""
    registry = PipelineEventRegistry()

    # Register the plugin class
    register_plugin_class(ExternalPluginA, registry=registry)

    # Apply to event bus and verify
    event_bus = EventBus()
    registry.apply(event_bus)

    context = PipelineContext(
        source_code="",
        file_path="<test>",
        result={},
        source_lines=[],
    )
    event_bus.emit("pre_analysis", context)

    assert context.result.get("external_a_called") is True


def test_register_multiple_plugins() -> None:
    """Test registering multiple plugins programmatically."""
    registry = PipelineEventRegistry()

    # Register multiple plugins
    register_plugin(ExternalPluginA(), registry=registry)
    register_plugin_class(ExternalPluginB, registry=registry)

    # Apply to event bus
    event_bus = EventBus()
    registry.apply(event_bus)

    context = PipelineContext(
        source_code="",
        file_path="<test>",
        result={},
        source_lines=[],
    )

    event_bus.emit("pre_analysis", context)
    assert context.result.get("external_a_called") is True

    event_bus.emit("post_analysis", context)
    assert context.result.get("external_b_called") is True


def test_register_plugin_uses_global_registry_by_default() -> None:
    """Test that register_plugin uses global registry when none is provided."""
    from src.core.pipeline.events import get_pipeline_event_registry

    global_registry = get_pipeline_event_registry()

    # Clear any previous state
    global_registry._handlers.clear()
    global_registry._plugins_loaded = False

    plugin = ExternalPluginA()
    register_plugin(plugin)  # No registry argument -> uses global

    # Verify it's in the global registry
    event_bus = EventBus()
    global_registry.apply(event_bus)

    context = PipelineContext(
        source_code="",
        file_path="<test>",
        result={},
        source_lines=[],
    )
    event_bus.emit("pre_analysis", context)

    assert context.result.get("external_a_called") is True


def test_discover_plugins_from_custom_package() -> None:
    """Test discovering plugins from a custom package path."""
    registry = PipelineEventRegistry()

    # Discover plugins from the default src.plugins package
    discovered = discover_plugins(
        package_name="src.plugins.pipeline", registry=registry
    )

    # Should discover at least the DefaultPipelineEventPlugin
    assert "pipeline_default" in discovered


def test_discover_plugins_graceful_failure() -> None:
    """Test that discovery fails gracefully for non-existent packages."""
    registry = PipelineEventRegistry()

    discovered = discover_plugins(
        package_name="non.existent.plugin.package", registry=registry
    )

    assert discovered == []


def test_plugin_isolation_across_registries() -> None:
    """Test that plugins registered in one registry don't affect another."""
    registry_a = PipelineEventRegistry()
    registry_b = PipelineEventRegistry()

    # Register plugin only in registry A
    register_plugin(ExternalPluginA(), registry=registry_a)

    # Apply both registries to separate event buses
    bus_a = EventBus()
    bus_b = EventBus()
    registry_a.apply(bus_a)
    registry_b.apply(bus_b)

    context = PipelineContext(
        source_code="",
        file_path="<test>",
        result={},
        source_lines=[],
    )

    # Bus A should trigger the plugin
    bus_a.emit("pre_analysis", context)
    assert context.result.get("external_a_called") is True

    # Bus B should NOT trigger the plugin
    context.result.clear()
    bus_b.emit("pre_analysis", context)
    assert context.result.get("external_a_called") is None

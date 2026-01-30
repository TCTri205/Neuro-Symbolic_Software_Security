# Plugin Registration Guide

## Overview

NSSS provides a first-class plugin registration system that allows external code to extend the analysis pipeline without modifying core files. Plugins can hook into various pipeline stages (pre/post analysis, IR, CFG, SSA, taint analysis, etc.) to inject custom logic, collect metrics, or modify behavior.

## Quick Start

### 1. Define Your Plugin

```python
from src.core.pipeline.events import PipelineContext, PipelineEventRegistry
from src.plugins.base import PipelineEventPlugin


class MyCustomPlugin(PipelineEventPlugin):
    @property
    def name(self) -> str:
        return "my_custom_plugin"

    def register(self, registry: PipelineEventRegistry) -> None:
        # Hook into pipeline events
        registry.register("pre_analysis", self.on_pre_analysis)
        registry.register("post_ssa", self.on_post_ssa)

    def on_pre_analysis(self, context: PipelineContext) -> None:
        print(f"Analyzing: {context.file_path}")
        # Custom gatekeeper logic
        if len(context.source_lines) > 10000:
            context.result.errors.append("File too large")
            context.stop()

    def on_post_ssa(self, context: PipelineContext) -> None:
        # Post-SSA enrichment
        if context.result.cfg:
            print(f"CFG has {len(context.result.cfg._blocks)} blocks")
```

### 2. Register Your Plugin

#### Option A: Programmatic Registration (Recommended)

```python
from src.core.pipeline import register_plugin

# Register a plugin instance
register_plugin(MyCustomPlugin())
```

#### Option B: Class Registration (Auto-instantiation)

```python
from src.core.pipeline import register_plugin_class

# Register a plugin class (will be instantiated automatically)
register_plugin_class(MyCustomPlugin)
```

#### Option C: Package Discovery

Organize plugins in a package and use auto-discovery:

```python
from src.core.pipeline import discover_plugins

# Discover all plugins in a custom package
discovered = discover_plugins("my_project.plugins")
print(f"Registered: {discovered}")
```

## Plugin Lifecycle

### Available Events

The pipeline emits events at each stage:

- `pre_analysis` - Before any analysis starts
- `static_scan` - After static scan (secrets, obfuscation)
- `pre_semgrep`, `semgrep`, `post_semgrep` - Semgrep stages
- `pre_ir`, `ir`, `post_ir` - Intermediate Representation
- `pre_graph_build`, `graph_build`, `post_graph_build` - CFG/Call Graph
- `pre_baseline`, `baseline`, `post_baseline` - Baseline filtering
- `pre_ssa`, `ssa`, `post_ssa` - Static Single Assignment
- `pre_taint`, `taint`, `post_taint` - Taint analysis
- `pre_llm`, `llm`, `post_llm` - LLM-based analysis
- `pre_privacy`, `privacy`, `post_privacy` - Privacy masking
- `post_analysis` - After all analysis completes

### PipelineContext API

Handlers receive a `PipelineContext` object:

```python
@dataclass
class PipelineContext:
    source_code: str          # Source code being analyzed
    file_path: str            # File path
    result: AnalysisResult    # Mutable result object
    source_lines: List[str]   # Source split into lines
    stop_processing: bool     # Set via stop() to halt pipeline

    def stop(self) -> None:   # Stop further processing
        self.stop_processing = True
```

### Modifying Results

Plugins can mutate `context.result`:

```python
def on_post_ssa(self, context: PipelineContext) -> None:
    # Add custom errors
    context.result.errors.append("Custom warning")

    # Modify CFG blocks
    if context.result.cfg:
        for block in context.result.cfg._blocks.values():
            block.llm_insights.append("Custom insight")

    # Store custom state
    if not hasattr(context, "_my_plugin_state"):
        context._my_plugin_state = {}
    context._my_plugin_state["metrics"] = {"blocks": len(context.result.cfg._blocks)}
```

## Advanced Usage

### Registry Isolation

Create isolated registries for testing or multi-tenant scenarios:

```python
from src.core.pipeline.events import PipelineEventRegistry

# Create isolated registry
registry = PipelineEventRegistry()
register_plugin(MyCustomPlugin(), registry=registry)

# Use with orchestrator
from src.core.pipeline import AnalysisOrchestrator

orchestrator = AnalysisOrchestrator(
    scan_factory=scan_factory,
    graph_factory=graph_factory,
    analysis_factory=analysis_factory,
    event_registry=registry,  # Use isolated registry
)
```

### Plugin State Management

Store state across events using the context:

```python
class StatefulPlugin(PipelineEventPlugin):
    @property
    def name(self) -> str:
        return "stateful"

    def register(self, registry: PipelineEventRegistry) -> None:
        registry.register("pre_analysis", self.on_pre)
        registry.register("post_ssa", self.on_post)

    def on_pre(self, context: PipelineContext) -> None:
        import time
        context._start_time = time.time()

    def on_post(self, context: PipelineContext) -> None:
        if hasattr(context, "_start_time"):
            duration = time.time() - context._start_time
            print(f"Analysis took {duration:.2f}s")
```

### Conditional Plugin Registration

Register plugins based on environment or configuration:

```python
import os

if os.getenv("ENABLE_METRICS_PLUGIN"):
    register_plugin(MetricsCollectorPlugin())

if os.getenv("ENABLE_CUSTOM_GATEKEEPER"):
    register_plugin(CustomGatekeeperPlugin())
```

## Testing Your Plugin

```python
from src.core.pipeline.events import EventBus, PipelineContext, PipelineEventRegistry


def test_my_plugin():
    # Setup
    registry = PipelineEventRegistry()
    register_plugin(MyCustomPlugin(), registry=registry)

    event_bus = EventBus()
    registry.apply(event_bus)

    # Create test context
    context = PipelineContext(
        source_code="x = 1",
        file_path="test.py",
        result=AnalysisResult(file_path="test.py"),
        source_lines=["x = 1"],
    )

    # Emit event
    event_bus.emit("pre_analysis", context)

    # Assert
    assert not context.result.errors
```

## Real-World Examples

### Example 1: Metrics Collection Plugin

```python
import time
from typing import Dict, Any


class MetricsPlugin(PipelineEventPlugin):
    def __init__(self):
        self.metrics: Dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "metrics_collector"

    def register(self, registry: PipelineEventRegistry) -> None:
        registry.register("pre_analysis", self._on_pre_analysis)
        registry.register("post_analysis", self._on_post_analysis)

    def _on_pre_analysis(self, context: PipelineContext) -> None:
        context._metrics_start = time.time()

    def _on_post_analysis(self, context: PipelineContext) -> None:
        if hasattr(context, "_metrics_start"):
            duration = time.time() - context._metrics_start
            self.metrics[context.file_path] = {
                "duration_ms": duration * 1000,
                "lines": len(context.source_lines),
                "errors": len(context.result.errors),
            }
```

### Example 2: Custom Gatekeeper

```python
class MaxLinesGatekeeperPlugin(PipelineEventPlugin):
    def __init__(self, max_lines: int = 5000):
        self.max_lines = max_lines

    @property
    def name(self) -> str:
        return "max_lines_gatekeeper"

    def register(self, registry: PipelineEventRegistry) -> None:
        registry.register("pre_analysis", self._check_max_lines)

    def _check_max_lines(self, context: PipelineContext) -> None:
        if len(context.source_lines) > self.max_lines:
            msg = f"File exceeds {self.max_lines} lines"
            context.result.errors.append(msg)
            context.stop()
```

### Example 3: Custom Report Generator

```python
import json


class JSONReportPlugin(PipelineEventPlugin):
    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    @property
    def name(self) -> str:
        return "json_reporter"

    def register(self, registry: PipelineEventRegistry) -> None:
        registry.register("post_analysis", self._generate_report)

    def _generate_report(self, context: PipelineContext) -> None:
        if not context.result.cfg:
            return

        report = {
            "file": context.file_path,
            "blocks": len(context.result.cfg._blocks),
            "errors": context.result.errors,
        }

        import os
        os.makedirs(self.output_dir, exist_ok=True)
        output_path = os.path.join(self.output_dir, "report.json")
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
```

## Migration from Legacy Code

If you were previously modifying core files to add hooks:

**Before (modifying core):**
```python
# src/core/pipeline/orchestrator.py
def analyze(self, source_code, file_path):
    # Direct modification
    my_custom_hook(source_code)
    ...
```

**After (plugin):**
```python
# my_plugin.py
class MyPlugin(PipelineEventPlugin):
    @property
    def name(self) -> str:
        return "my_plugin"

    def register(self, registry: PipelineEventRegistry) -> None:
        registry.register("pre_analysis", self.my_custom_hook)

    def my_custom_hook(self, context: PipelineContext) -> None:
        # Same logic, no core modification
        ...

# main.py
from src.core.pipeline import register_plugin
register_plugin(MyPlugin())
```

## API Reference

### Functions

#### `register_plugin(plugin, registry=None)`
Register a plugin instance programmatically.

**Parameters:**
- `plugin: PipelineEventPlugin` - Plugin instance
- `registry: Optional[PipelineEventRegistry]` - Target registry (uses global if None)

#### `register_plugin_class(plugin_class, registry=None)`
Register a plugin class (auto-instantiation).

**Parameters:**
- `plugin_class: Type[PipelineEventPlugin]` - Plugin class
- `registry: Optional[PipelineEventRegistry]` - Target registry (uses global if None)

#### `discover_plugins(package_name, registry=None)`
Discover and register plugins from a package.

**Parameters:**
- `package_name: str` - Package to scan (e.g., "my_plugins")
- `registry: Optional[PipelineEventRegistry]` - Target registry (uses global if None)

**Returns:** `List[str]` - Names of registered plugins

### Interfaces

#### `PipelineEventPlugin` (Protocol)

```python
class PipelineEventPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin name."""
        pass

    @abstractmethod
    def register(self, registry: PipelineEventRegistry) -> None:
        """Register event handlers."""
        pass
```

## Best Practices

1. **Unique Names**: Use descriptive, unique plugin names (e.g., `"my_company_metrics_v2"`)
2. **Error Handling**: Wrap handler logic in try/except to avoid breaking the pipeline
3. **State Isolation**: Store plugin-specific state on the context with prefixed attributes (e.g., `context._myplugin_state`)
4. **Graceful Degradation**: Don't assume result fields exist; check before accessing
5. **Testing**: Always test plugins in isolation before deploying
6. **Documentation**: Document which events your plugin listens to and what it modifies

## Troubleshooting

### Plugin Not Triggered

- ✅ Verify plugin is registered before orchestrator creates event bus
- ✅ Check event name spelling (e.g., `"pre_analysis"` not `"pre-analysis"`)
- ✅ Ensure `register()` method calls `registry.register(event, handler)`

### Import Errors

```python
# ✅ Correct
from src.core.pipeline import register_plugin
from src.plugins.base import PipelineEventPlugin

# ❌ Incorrect
from src.core.pipeline.events import register_plugin  # Not exported from events.py
```

### State Not Persisting

- ✅ Store state on `context` object (shared across handlers)
- ❌ Don't store state on plugin instance (may be instantiated multiple times)

## See Also

- [Pipeline Architecture](./01_Architecture.md)
- [EventBus Design](./06_EventBus.md)
- [Testing Guide](./09_Testing.md)

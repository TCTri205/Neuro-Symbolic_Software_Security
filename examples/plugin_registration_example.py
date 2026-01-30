"""
Example: Custom Plugin Registration

This example demonstrates how to create and register a custom plugin
without modifying core NSSS code.
"""

from src.core.pipeline import register_plugin
from src.core.pipeline.events import PipelineContext, PipelineEventRegistry
from src.plugins.base import PipelineEventPlugin


class SimpleLoggingPlugin(PipelineEventPlugin):
    """
    Example plugin that logs analysis progress.
    """

    @property
    def name(self) -> str:
        return "simple_logger"

    def register(self, registry: PipelineEventRegistry) -> None:
        # Hook into key pipeline events
        registry.register("pre_analysis", self.on_pre_analysis)
        registry.register("post_ssa", self.on_post_ssa)
        registry.register("post_analysis", self.on_post_analysis)

    def on_pre_analysis(self, context: PipelineContext) -> None:
        print(f"[SimpleLogger] Starting analysis: {context.file_path}")

    def on_post_ssa(self, context: PipelineContext) -> None:
        if context.result.cfg:
            print(
                f"[SimpleLogger] SSA complete: {len(context.result.cfg._blocks)} blocks"
            )

    def on_post_analysis(self, context: PipelineContext) -> None:
        error_count = len(context.result.errors)
        if error_count > 0:
            print(f"[SimpleLogger] Analysis complete with {error_count} errors")
        else:
            print("[SimpleLogger] Analysis complete: SUCCESS")


if __name__ == "__main__":
    # Register the plugin
    print("Registering SimpleLoggingPlugin...")
    register_plugin(SimpleLoggingPlugin())
    print("Plugin registered successfully!")

    # Now run your analysis pipeline
    # The plugin will automatically hook into events
    print("\nPlugin is now active and will log pipeline events.")
    print("Run the NSSS pipeline to see the plugin in action.")

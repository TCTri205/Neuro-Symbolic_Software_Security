from dataclasses import dataclass


@dataclass
class SummarizationPolicy:
    """
    Decides whether to summarize or mark unscannable.
    Prefers summarization over skipping.
    """

    max_nodes: int = 2000
    max_lines: int = 2000

    def decide(self, node_count: int, line_count: int) -> str:
        if node_count > self.max_nodes or line_count > self.max_lines:
            return "summarize"
        return "analyze"

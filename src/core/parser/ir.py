from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class IRSpan(BaseModel):
    file: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int


class IRNode(BaseModel):
    id: str
    kind: str
    span: IRSpan
    parent_id: Optional[str]
    scope_id: Optional[str]
    attrs: Dict[str, Any] = Field(default_factory=dict)


class IREdge(BaseModel):
    from_id: str = Field(..., alias="from")
    to: str
    type: str
    guard_id: Optional[str]


class IRSymbol(BaseModel):
    name: str
    kind: str
    scope_id: str
    defs: List[str] = Field(default_factory=list)
    uses: List[str] = Field(default_factory=list)


class IRGraph(BaseModel):
    nodes: List[IRNode] = Field(default_factory=list)
    edges: List[IREdge] = Field(default_factory=list)
    symbols: List[IRSymbol] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)

    def add_node(self, node: IRNode) -> str:
        self.nodes.append(node)
        return node.id

    def add_edge(self, edge: IREdge) -> None:
        self.edges.append(edge)


def extract_source_code(source: str, span: IRSpan) -> str:
    """
    Extract the source code segment corresponding to the given IRSpan.
    Handles UTF-8 byte offsets correctly.
    """
    if span.start_line == -1 or span.start_col == -1:
        return ""

    lines = source.splitlines(keepends=True)

    # 1-based line index check
    if span.start_line < 1 or span.start_line > len(lines):
        return ""

    # If end_line is missing or invalid, we can't extract safely.
    # However, if start is valid, we might return something?
    # For now, stricter is better.
    if span.end_line == -1:
        # Fallback: return the rest of the start line?
        # Or just empty. Let's return empty to avoid noise.
        return ""

    if span.end_line < span.start_line or span.end_line > len(lines):
        return ""

    if span.start_line == span.end_line:
        line = lines[span.start_line - 1]
        line_bytes = line.encode("utf-8")
        # span.end_col can be -1 if unknown, but usually if end_line is known, end_col is too.
        # If end_col is -1, maybe take till end of line?
        if span.end_col == -1:
            return line_bytes[span.start_col :].decode("utf-8")
        return line_bytes[span.start_col : span.end_col].decode("utf-8")

    # Multi-line
    first_line = lines[span.start_line - 1]
    first_part = first_line.encode("utf-8")[span.start_col :].decode("utf-8")

    middle_parts = lines[span.start_line : span.end_line - 1]

    last_line = lines[span.end_line - 1]
    last_part_bytes = last_line.encode("utf-8")
    if span.end_col == -1:
        last_part = last_line
    else:
        last_part = last_part_bytes[: span.end_col].decode("utf-8")

    return first_part + "".join(middle_parts) + last_part

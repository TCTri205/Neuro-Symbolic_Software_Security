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

import ast
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict
import networkx as nx


class PhiNode(BaseModel):
    var_name: str
    result: str  # The new version, e.g., "x_3"
    operands: Dict[int, str] = Field(
        default_factory=dict
    )  # block_id -> version, e.g. {1: "x_1", 2: "x_2"}

    def __repr__(self):
        args = ", ".join(f"B{k}:{v}" for k, v in self.operands.items())
        return f"{self.result} = phi({args})"


class BasicBlock(BaseModel):
    id: int
    scope: str = "global"
    statements: List[Any] = Field(default_factory=list)  # Storing AST nodes
    phi_nodes: List[PhiNode] = Field(default_factory=list)
    security_findings: List[Dict[str, Any]] = Field(default_factory=list)
    llm_insights: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def add_statement(self, stmt: ast.AST):
        self.statements.append(stmt)

    def add_phi(self, phi: PhiNode):
        self.phi_nodes.append(phi)

    def __repr__(self):
        return f"Block(id={self.id}, stmts={len(self.statements)}, phis={len(self.phi_nodes)})"


class ControlFlowGraph:
    def __init__(self, name: str):
        self.name = name
        self.graph = nx.DiGraph()
        self.entry_block: Optional[BasicBlock] = None
        self.exit_block: Optional[BasicBlock] = None
        self._blocks = {}
        self.scopes: Dict[str, Any] = {}  # scope_name -> AST node (FunctionDef, etc)

    def add_block(self, block: BasicBlock):
        self._blocks[block.id] = block
        self.graph.add_node(block.id, data=block)

    def add_edge(self, source_id: int, target_id: int, label: Optional[str] = None):
        self.graph.add_edge(source_id, target_id, label=label)

    def get_block(self, block_id: int) -> Optional[BasicBlock]:
        return self._blocks.get(block_id)

    @property
    def nodes(self):
        return self.graph.nodes

    @property
    def edges(self):
        return self.graph.edges

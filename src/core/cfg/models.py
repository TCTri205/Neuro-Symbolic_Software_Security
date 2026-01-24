import ast
from typing import List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
import networkx as nx

class BasicBlock(BaseModel):
    id: int
    statements: List[Any] = Field(default_factory=list) # Storing AST nodes
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def add_statement(self, stmt: ast.AST):
        self.statements.append(stmt)
    
    def __repr__(self):
        return f"Block(id={self.id}, stmts={len(self.statements)})"

class ControlFlowGraph:
    def __init__(self, name: str):
        self.name = name
        self.graph = nx.DiGraph()
        self.entry_block: Optional[BasicBlock] = None
        self.exit_block: Optional[BasicBlock] = None
        self._blocks = {}
    
    def add_block(self, block: BasicBlock):
        self._blocks[block.id] = block
        self.graph.add_node(block.id, data=block)
        
    def add_edge(self, source_id: int, target_id: int, label: str = None):
        self.graph.add_edge(source_id, target_id, label=label)
        
    def get_block(self, block_id: int) -> BasicBlock:
        return self._blocks.get(block_id)

    @property
    def nodes(self):
        return self.graph.nodes
    
    @property
    def edges(self):
        return self.graph.edges

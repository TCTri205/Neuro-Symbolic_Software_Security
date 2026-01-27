from typing import List, Dict, Optional, Union
import ast
from pydantic import BaseModel, Field
from .models import ControlFlowGraph, BasicBlock


class FunctionSignature(BaseModel):
    name: str
    inputs: List[Dict[str, str]]  # [{"name": "x", "type": "int"}]
    outputs: List[str]  # ["int"]
    calls: List[str]  # ["print", "calculate"]
    complexity: int = 1
    side_effects: List[str] = Field(
        default_factory=list
    )  # ["global:write:x", "io:print"]
    taint_sources: List[str] = Field(default_factory=list)  # ["arg:password"]
    taint_sinks: List[str] = Field(default_factory=list)  # ["call:execute"]


class SignatureExtractor:
    def __init__(self, cfg: ControlFlowGraph):
        self.cfg = cfg

    def extract(self) -> List[FunctionSignature]:
        signatures = []
        # Group blocks by scope
        blocks_by_scope: Dict[str, List[BasicBlock]] = {}
        for block in self.cfg._blocks.values():
            if block.scope not in blocks_by_scope:
                blocks_by_scope[block.scope] = []
            blocks_by_scope[block.scope].append(block)

        for scope_name, blocks in blocks_by_scope.items():
            # Retrieve AST node for this scope if available
            scope_node = self.cfg.scopes.get(scope_name)

            # We skip global scope for function signatures unless we treat it as a script entry
            if scope_name == self.cfg.name:
                continue

            # We process FunctionDef and AsyncFunctionDef
            if isinstance(scope_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = self._analyze_function(scope_name, scope_node, blocks)
                signatures.append(sig)

        return signatures

    def _analyze_function(
        self,
        name: str,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        blocks: List[BasicBlock],
    ) -> FunctionSignature:
        # 1. Inputs
        inputs = []
        if node.args.args:
            for arg in node.args.args:
                arg_type = "Any"
                if arg.annotation:
                    arg_type = ast.unparse(arg.annotation)
                inputs.append({"name": arg.arg, "type": arg_type})

        # 2. Outputs
        outputs = []
        if node.returns:
            outputs.append(ast.unparse(node.returns))

        if not outputs:
            outputs = ["Any"]

        # 3. Calls & Complexity & Side Effects
        calls = set()
        complexity = 0
        side_effects = set()

        # Check for global writes (Global keyword in function body)
        for stmt in node.body:
            if isinstance(stmt, ast.Global):
                for global_name in stmt.names:
                    side_effects.add(f"global:write:{global_name}")

        for block in blocks:
            # Estimate complexity: count branching (2 edges out)
            if self.cfg.graph.has_node(block.id):
                if self.cfg.graph.out_degree(block.id) > 1:
                    complexity += 1

            for stmt in block.statements:
                for subnode in ast.walk(stmt):
                    if isinstance(subnode, ast.Call):
                        func_name = self._get_func_name(subnode)
                        if func_name:
                            calls.add(func_name)
                            # Simple heuristic for side effects
                            if func_name == "print":
                                side_effects.add("io:print")
                            elif func_name in ["open", "write"]:
                                side_effects.add(f"io:{func_name}")
                            elif func_name.startswith(
                                "requests."
                            ) or func_name.startswith("urllib."):
                                side_effects.add(f"net:{func_name}")

        return FunctionSignature(
            name=name,
            inputs=inputs,
            outputs=outputs,
            calls=sorted(list(calls)),
            complexity=complexity + 1,  # +1 for base path
            side_effects=sorted(list(side_effects)),
            taint_sources=[],  # Placeholder for future taint analysis
            taint_sinks=[],  # Placeholder for future taint analysis
        )

    def _get_func_name(self, call_node: ast.Call) -> Optional[str]:
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            try:
                return ast.unparse(call_node.func)
            except Exception:
                return call_node.func.attr
        return None

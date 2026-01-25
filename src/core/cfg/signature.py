from typing import List, Dict, Optional, Union
import ast
from pydantic import BaseModel
from .models import ControlFlowGraph, BasicBlock


class FunctionSignature(BaseModel):
    name: str
    inputs: List[Dict[str, str]]  # [{"name": "x", "type": "int"}]
    outputs: List[str]  # ["int"]
    calls: List[str]  # ["print", "calculate"]
    complexity: int = 1


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

        # 3. Calls & Complexity
        calls = set()
        complexity = 0

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

        return FunctionSignature(
            name=name,
            inputs=inputs,
            outputs=outputs,
            calls=sorted(list(calls)),
            complexity=complexity + 1,  # +1 for base path
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

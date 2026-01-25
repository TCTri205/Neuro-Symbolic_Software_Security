import ast
import networkx as nx
from typing import Dict, List, Set, Any, Optional
from .models import ControlFlowGraph, BasicBlock

class CallGraph:
    """
    Represents the Call Graph of the program.
    Nodes are function/method names.
    Edges represent calls (Caller -> Callee).
    """
    def __init__(self):
        self.graph = nx.DiGraph()
        # Registry of class methods for speculative dispatch
        # format: { "ClassName": {"method1", "method2"} }
        self.class_hierarchy: Dict[str, Set[str]] = {}
        
    def register_class(self, class_name: str, methods: List[str]):
        """Registers a class and its methods for lookup."""
        if class_name not in self.class_hierarchy:
            self.class_hierarchy[class_name] = set()
        self.class_hierarchy[class_name].update(methods)
        
    def add_node(self, name: str, kind: str = "function"):
        """Adds a node to the graph."""
        if name not in self.graph:
            self.graph.add_node(name, kind=kind)
            
    def add_edge(self, caller: str, callee: str, edge_type: str = "direct"):
        """
        Adds a call edge.
        edge_type can be 'direct' or 'speculative'.
        """
        self.graph.add_edge(caller, callee, type=edge_type)
        
    def get_potential_callees(self, method_name: str) -> List[str]:
        """
        Returns a list of fully qualified method names (ClassName.method_name)
        that match the given method_name from the class hierarchy.
        Used for speculative expansion.
        """
        candidates = []
        for cls, methods in self.class_hierarchy.items():
            if method_name in methods:
                candidates.append(f"{cls}.{method_name}")
        return candidates

class CallFinder(ast.NodeVisitor):
    """
    Helper to find Call nodes within an AST tree.
    """
    def __init__(self):
        self.calls = []
        
    def visit_Call(self, node: ast.Call):
        call_info = {
            "node": node,
            "kind": "unknown",
            "name": None,
            "base": None
        }
        
        if isinstance(node.func, ast.Name):
            call_info["kind"] = "function"
            call_info["name"] = node.func.id
        elif isinstance(node.func, ast.Attribute):
            call_info["kind"] = "method"
            call_info["name"] = node.func.attr
            if isinstance(node.func.value, ast.Name):
                call_info["base"] = node.func.value.id
            else:
                call_info["base"] = "<complex>" # e.g. get_obj().method()
                
        self.calls.append(call_info)
        self.generic_visit(node)

class CallGraphBuilder:
    """
    Builds the CallGraph from CFGs.
    """
    def __init__(self, call_graph: CallGraph):
        self.cg = call_graph
        
    def extract_definitions(self, tree: ast.AST):
        """
        First pass: Scan AST for Class/Function definitions to populate registry.
        """
        scanner = DefinitionScanner(self.cg)
        scanner.visit(tree)
        
    def build_from_cfg(self, cfg: ControlFlowGraph):
        """
        Second pass: Scan CFG blocks for calls and add edges.
        """
        # Ensure the module node exists
        self.cg.add_node(cfg.name)
        
        for block in cfg._blocks.values():
            # The caller is the scope of the block (e.g., function name or module name)
            caller = block.scope
            self.cg.add_node(caller)
            
            for stmt in block.statements:
                self._process_statement(caller, stmt)
                
    def _process_statement(self, caller: str, stmt: ast.AST):
        finder = CallFinder()
        finder.visit(stmt)
        
        for call in finder.calls:
            if call["kind"] == "function":
                # Direct function call
                callee = call["name"]
                self.cg.add_node(callee)
                self.cg.add_edge(caller, callee, edge_type="direct")
                
            elif call["kind"] == "method":
                # Method call - Check for Speculative Dispatch
                method_name = call["name"]
                base_obj = call["base"]
                
                # If we knew the type of base_obj, we could be specific.
                # For now, we use the Speculative Expansion logic:
                # Add edges to ALL classes that implement this method.
                
                candidates = self.cg.get_potential_callees(method_name)
                
                if candidates:
                    for cand in candidates:
                        self.cg.add_node(cand, kind="method")
                        self.cg.add_edge(caller, cand, edge_type="speculative")
                else:
                    # If no candidates found (external lib or untracked), add generic node
                    callee = f"?.{method_name}"
                    self.cg.add_node(callee, kind="external")
                    self.cg.add_edge(caller, callee, edge_type="direct")

class DefinitionScanner(ast.NodeVisitor):
    """
    Scans for Class and Function definitions to populate the CallGraph registry.
    """
    def __init__(self, cg: CallGraph):
        self.cg = cg
        self.current_class = None
        
    def visit_ClassDef(self, node: ast.ClassDef):
        prev_class = self.current_class
        self.current_class = node.name
        
        # Collect methods
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)
        
        self.cg.register_class(node.name, methods)
        
        self.generic_visit(node)
        self.current_class = prev_class
        
    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Could also register standalone functions if needed
        self.generic_visit(node)

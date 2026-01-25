import ast
from .models import ControlFlowGraph, BasicBlock

class CFGBuilder(ast.NodeVisitor):
    def __init__(self):
        self.cfg: ControlFlowGraph = None
        self.current_block: BasicBlock = None
        self.counter = 0
        
    def _new_block(self) -> BasicBlock:
        self.counter += 1
        block = BasicBlock(id=self.counter)
        self.cfg.add_block(block)
        return block

    def build(self, name: str, node: ast.AST) -> ControlFlowGraph:
        self.cfg = ControlFlowGraph(name)
        self.entry_block = self._new_block()
        self.cfg.entry_block = self.entry_block
        self.current_block = self.entry_block
        
        self.visit(node)
        
        # Ensure the last block is marked or connected if needed
        # For now, just return what we have
        return self.cfg

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Handle arguments as assignments in the entry block
        if node.args.args:
            for arg in node.args.args:
                # Treat argument as an assignment: arg.arg = <param>
                # We store the arg node itself as a statement representing definition
                self.current_block.add_statement(arg)
                
        # In this simplified builder, we assume we are building CFG for the function body
        # If the input node IS a FunctionDef, we process its body
        for stmt in node.body:
            self.visit(stmt)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # Similar to FunctionDef
        if node.args.args:
            for arg in node.args.args:
                self.current_block.add_statement(arg)
                
        for stmt in node.body:
            self.visit(stmt)

    def visit_Module(self, node: ast.Module):
        # Similar to FunctionDef, process body
        for stmt in node.body:
            self.visit(stmt)

    def visit_If(self, node: ast.If):
        # 1. Finish current block with the condition (conceptually)
        # Actually, the condition should be in the current block (or a new header block)
        # For simplicity: Add condition to current block, then branch
        self.current_block.add_statement(node.test)
        
        pred_block = self.current_block
        
        # 2. Create branches
        then_block = self._new_block()
        else_block = self._new_block() if node.orelse else None
        join_block = self._new_block()
        
        # 3. Process Then
        self.cfg.add_edge(pred_block.id, then_block.id, label="True")
        self.current_block = then_block
        for stmt in node.body:
            self.visit(stmt)
        # Link end of then to join
        self.cfg.add_edge(self.current_block.id, join_block.id)
        
        # 4. Process Else
        if else_block:
            self.cfg.add_edge(pred_block.id, else_block.id, label="False")
            self.current_block = else_block
            for stmt in node.orelse:
                self.visit(stmt)
            # Link end of else to join
            self.cfg.add_edge(self.current_block.id, join_block.id)
        else:
            # If no else, False goes directly to join
            self.cfg.add_edge(pred_block.id, join_block.id, label="False")
            
        # 5. Continue from join
        self.current_block = join_block

    def visit_While(self, node: ast.While):
        # 1. Header block (Condition)
        # We need a split here. 
        # If current block is not empty, we might want to split or just link.
        # Let's link current to a new header.
        
        header_block = self._new_block()
        self.cfg.add_edge(self.current_block.id, header_block.id)
        
        header_block.add_statement(node.test)
        
        body_block = self._new_block()
        exit_block = self._new_block()
        
        # Link Header -> Body (True)
        self.cfg.add_edge(header_block.id, body_block.id, label="True")
        
        # Link Header -> Exit (False)
        self.cfg.add_edge(header_block.id, exit_block.id, label="False")
        
        # Process Body
        self.current_block = body_block
        for stmt in node.body:
            self.visit(stmt)
            
        # Link Body End -> Header (Loop back)
        self.cfg.add_edge(self.current_block.id, header_block.id)
        
        # Continue from Exit
        self.current_block = exit_block

    def visit_For(self, node: ast.For):
        # Similar to While but with Iterator
        header_block = self._new_block()
        self.cfg.add_edge(self.current_block.id, header_block.id)
        
        # Represent the iterator logic
        header_block.add_statement(node.target) # roughly
        header_block.add_statement(node.iter)
        
        body_block = self._new_block()
        exit_block = self._new_block()
        
        self.cfg.add_edge(header_block.id, body_block.id, label="Next")
        self.cfg.add_edge(header_block.id, exit_block.id, label="Stop")
        
        self.current_block = body_block
        for stmt in node.body:
            self.visit(stmt)
            
        self.cfg.add_edge(self.current_block.id, header_block.id)
        self.current_block = exit_block

    def visit_AsyncFor(self, node: ast.AsyncFor):
        # Same structure as For
        header_block = self._new_block()
        self.cfg.add_edge(self.current_block.id, header_block.id)
        
        header_block.add_statement(node.target)
        header_block.add_statement(node.iter)
        
        body_block = self._new_block()
        exit_block = self._new_block()
        
        self.cfg.add_edge(header_block.id, body_block.id, label="Next")
        self.cfg.add_edge(header_block.id, exit_block.id, label="Stop")
        
        self.current_block = body_block
        for stmt in node.body:
            self.visit(stmt)
            
        self.cfg.add_edge(self.current_block.id, header_block.id)
        self.current_block = exit_block

    # Default visitor for flat statements
    def generic_visit(self, node):
        if isinstance(node, (ast.Assign, ast.Expr, ast.Return, ast.AugAssign, ast.AnnAssign)):
             self.current_block.add_statement(node)
        else:
            super().generic_visit(node)

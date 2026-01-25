import ast
from .models import ControlFlowGraph, BasicBlock

class CFGBuilder(ast.NodeVisitor):
    def __init__(self):
        self.cfg: ControlFlowGraph = None
        self.current_block: BasicBlock = None
        self.counter = 0
        self.current_scope = "global"
        self.root_node = None
        
    def _new_block(self) -> BasicBlock:
        self.counter += 1
        block = BasicBlock(id=self.counter, scope=self.current_scope)
        self.cfg.add_block(block)
        return block

    def build(self, name: str, node: ast.AST) -> ControlFlowGraph:
        self.cfg = ControlFlowGraph(name)
        self.current_scope = name # Set scope to module name
        self.root_node = node
        self.entry_block = self._new_block()
        self.cfg.entry_block = self.entry_block
        self.current_block = self.entry_block
        
        self.visit(node)
        
        # Ensure the last block is marked or connected if needed
        # For now, just return what we have
        return self.cfg

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Save outer context
        outer_block = self.current_block
        previous_scope = self.current_scope
        
        # Switch to function scope
        self.current_scope = node.name
        
        # Create isolated entry block for the function
        func_entry = self._new_block()
        
        # Special case: If this function IS the root node being built (e.g. for unit tests),
        # we treat it as the entry point of execution and link it.
        if node is self.root_node and outer_block:
            self.cfg.add_edge(outer_block.id, func_entry.id, label="Entry")
            
        self.current_block = func_entry
        
        # Handle arguments
        if node.args.args:
            for arg in node.args.args:
                self.current_block.add_statement(arg)
                
        # Process body
        for stmt in node.body:
            self.visit(stmt)
            
        # Restore outer context
        self.current_scope = previous_scope
        
        # Continue flow in outer scope
        post_def_block = self._new_block()
        if outer_block:
             self.cfg.add_edge(outer_block.id, post_def_block.id, label="Next")
        self.current_block = post_def_block

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        outer_block = self.current_block
        previous_scope = self.current_scope
        
        self.current_scope = node.name
        
        func_entry = self._new_block()
        
        if node is self.root_node and outer_block:
            self.cfg.add_edge(outer_block.id, func_entry.id, label="Entry")
            
        self.current_block = func_entry
        
        if node.args.args:
            for arg in node.args.args:
                self.current_block.add_statement(arg)
                
        for stmt in node.body:
            self.visit(stmt)

        self.current_scope = previous_scope
        
        post_def_block = self._new_block()
        if outer_block:
             self.cfg.add_edge(outer_block.id, post_def_block.id, label="Next")
        self.current_block = post_def_block

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

    def visit_With(self, node: ast.With):
        # Add the 'with' context managers to the current block
        # as they are evaluated before entering the body.
        for item in node.items:
            self.current_block.add_statement(item.context_expr)
            if item.optional_vars:
                # This represents the 'as var' part, which is an assignment
                self.current_block.add_statement(item.optional_vars)
        
        # Process the body of the 'with' statement
        for stmt in node.body:
            self.visit(stmt)

    def visit_AsyncWith(self, node: ast.AsyncWith):
        for item in node.items:
            self.current_block.add_statement(item.context_expr)
            if item.optional_vars:
                self.current_block.add_statement(item.optional_vars)
        
        for stmt in node.body:
            self.visit(stmt)

    # Default visitor for flat statements
    def generic_visit(self, node):
        if isinstance(node, (ast.Assign, ast.Expr, ast.Return, ast.AugAssign, ast.AnnAssign)):
             self.current_block.add_statement(node)
        else:
            super().generic_visit(node)

import ast
from typing import Dict, Set
from .callgraph import CallGraph


class SyntheticEdgeBuilder(ast.NodeVisitor):
    """
    Detects and links implicit flows (Signals, MQ) by adding synthetic edges
    to the Call Graph.
    """

    def __init__(self, call_graph: CallGraph):
        self.cg = call_graph
        # Topic/Channel -> Set[Handler Function Names]
        self.mq_handlers: Dict[str, Set[str]] = {}
        # Signal Variable Name -> Set[Handler Function Names]
        # (Simplified approach: matching variable names for signals)
        self.signal_handlers: Dict[str, Set[str]] = {}

        self.current_scope = "global"

    def process(self, tree: ast.AST, cfg=None):
        """
        Main entry point.
        Pass 1: Detect Handlers (Subscribers)
        Pass 2: Detect Triggers (Publishers)
        """
        # We process the AST directly as it's easier to find call arguments than the CFG for now
        # Pass 1: Scan for subscriptions
        self.mode = "handlers"
        self.visit(tree)

        # Pass 2: Scan for publications and link
        self.mode = "triggers"
        self.visit(tree)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        prev_scope = self.current_scope
        self.current_scope = node.name
        self.generic_visit(node)
        self.current_scope = prev_scope

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        prev_scope = self.current_scope
        self.current_scope = node.name
        self.generic_visit(node)
        self.current_scope = prev_scope

    def visit_Call(self, node: ast.Call):
        if self.mode == "handlers":
            self._analyze_handler_registration(node)
        elif self.mode == "triggers":
            self._analyze_trigger_call(node)

        self.generic_visit(node)

    def _analyze_handler_registration(self, node: ast.Call):
        """
        Detects:
        - channel.basic_consume(queue='...', on_message_callback=func)
        - signal.connect(func)
        """
        # 1. RabbitMQ: basic_consume
        if self._is_method_call(node, "basic_consume"):
            queue = self._get_keyword_arg(node, "queue")
            callback = self._get_keyword_arg(node, "on_message_callback")

            if queue and callback:
                self._register_mq_handler(queue, callback)

        # 2. Blinker: .connect(func)
        # We assume the caller is the signal variable
        if isinstance(node.func, ast.Attribute) and node.func.attr == "connect":
            # Heuristic: The object being called is the signal variable
            signal_var = self._get_name_from_node(node.func.value)

            # Handler is usually the first arg
            handler = None
            if node.args:
                handler = self._get_name_from_node(node.args[0])

            if signal_var and handler:
                self._register_signal_handler(signal_var, handler)

    def _analyze_trigger_call(self, node: ast.Call):
        """
        Detects:
        - channel.basic_publish(..., routing_key='...', ...)
        - signal.send(...)
        """
        caller = self.current_scope

        # 1. RabbitMQ: basic_publish
        if self._is_method_call(node, "basic_publish"):
            routing_key = self._get_keyword_arg(node, "routing_key")
            if routing_key:
                self._link_mq(caller, routing_key)

        # 2. Blinker: .send(...)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "send":
            signal_var = self._get_name_from_node(node.func.value)
            if signal_var:
                self._link_signal(caller, signal_var)

    def _register_mq_handler(self, topic: str, handler: str):
        if topic not in self.mq_handlers:
            self.mq_handlers[topic] = set()
        self.mq_handlers[topic].add(handler)

    def _register_signal_handler(self, signal_var: str, handler: str):
        if signal_var not in self.signal_handlers:
            self.signal_handlers[signal_var] = set()
        self.signal_handlers[signal_var].add(handler)

    def _link_mq(self, caller: str, topic: str):
        if topic in self.mq_handlers:
            for handler in self.mq_handlers[topic]:
                self.cg.add_edge(caller, handler, edge_type="synthetic")
                # Store extra metadata about the edge if possible (CallGraph edge structure depends on implementation)
                # For now, we just add the edge.
                # If we want to store metadata, we might need to update CallGraph.add_edge to accept kwargs or set it directly.
                if self.cg.graph.has_edge(caller, handler):
                    self.cg.graph[caller][handler]["mechanism"] = "mq"

    def _link_signal(self, caller: str, signal_var: str):
        if signal_var in self.signal_handlers:
            for handler in self.signal_handlers[signal_var]:
                self.cg.add_edge(caller, handler, edge_type="synthetic")
                if self.cg.graph.has_edge(caller, handler):
                    self.cg.graph[caller][handler]["mechanism"] = "signal"

    # --- Helpers ---

    def _is_method_call(self, node: ast.Call, method_name: str) -> bool:
        if isinstance(node.func, ast.Attribute):
            return node.func.attr == method_name
        return False

    def _get_keyword_arg(self, node: ast.Call, arg_name: str) -> str | None:
        for kw in node.keywords:
            if kw.arg == arg_name:
                return self._get_literal_value(kw.value) or self._get_name_from_node(
                    kw.value
                )
        return None

    def _get_literal_value(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant):
            return str(node.value)
        return None

    def _get_name_from_node(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            # Recursively get name (e.g. self.handler -> handler, or keep full?)
            # For simplicity, let's just grab the attribute name if it looks like a function ref
            return node.attr
        return None

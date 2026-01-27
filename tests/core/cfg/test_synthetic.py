import ast
import unittest
from src.core.cfg.builder import CFGBuilder
from src.core.cfg.callgraph import CallGraph, CallGraphBuilder

# I will implement this module next
from src.core.cfg.synthetic import SyntheticEdgeBuilder


class TestSyntheticEdges(unittest.TestCase):
    def setUp(self):
        self.builder = CFGBuilder()

    def _build_graph(self, code: str, name: str = "test_module"):
        tree = ast.parse(code)

        # 1. Build CFG
        cfg = self.builder.build(name, tree)

        # 2. Build Call Graph (Base)
        cg = CallGraph()
        cg_builder = CallGraphBuilder(cg)
        cg_builder.extract_definitions(tree)
        cg_builder.build_from_cfg(cfg)

        # 3. Apply Synthetic Edges
        synth_builder = SyntheticEdgeBuilder(cg)
        synth_builder.process(tree, cfg)

        return cg

    def test_blinker_signals(self):
        code = """
import blinker

# Define signal
my_signal = blinker.signal('my-event')

# Handler
def on_event(sender):
    pass

# Connect
my_signal.connect(on_event)

# Trigger
def trigger_it():
    my_signal.send('sender-obj')
"""
        cg = self._build_graph(code)

        # Expect implicit edge from trigger_it -> on_event
        # Because:
        # 1. 'my_signal.connect(on_event)' registers 'on_event' to 'my_signal' (heuristic match on signal name/variable?)
        # 2. 'my_signal.send' triggers 'my_signal'

        # Note: Static analysis of variable values (like 'my_signal') is hard without dataflow.
        # But if we track "connect" and "send" on the SAME variable name in the same scope, or use a heuristic.
        # For this P1, let's assume we match on the VARIABLE NAME used to connect/send.

        self.assertTrue(cg.graph.has_edge("trigger_it", "on_event"))
        edge_data = cg.graph.get_edge_data("trigger_it", "on_event")
        self.assertEqual(edge_data["type"], "synthetic")
        self.assertEqual(edge_data["mechanism"], "signal")

    def test_pika_rabbitmq(self):
        code = """
import pika

def callback_func(ch, method, properties, body):
    process_data(body)

def process_data(d):
    pass

def setup_consumer():
    channel.basic_consume(queue='task_queue', on_message_callback=callback_func)

def produce_msg():
    channel.basic_publish(exchange='', routing_key='task_queue', body='Hello')
"""
        cg = self._build_graph(code)

        # Expect implicit edge from produce_msg -> callback_func
        # Key: "task_queue" string literal match.

        self.assertTrue(cg.graph.has_edge("produce_msg", "callback_func"))
        edge_data = cg.graph.get_edge_data("produce_msg", "callback_func")
        self.assertEqual(edge_data["type"], "synthetic")
        self.assertEqual(edge_data["mechanism"], "mq")


if __name__ == "__main__":
    unittest.main()

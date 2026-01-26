import ast
import unittest
from src.core.cfg.builder import CFGBuilder
from src.core.cfg.callgraph import CallGraph, CallGraphBuilder


class TestCallGraph(unittest.TestCase):
    def setUp(self):
        self.builder = CFGBuilder()

    def _build_cg(self, code: str, name: str = "test_module"):
        tree = ast.parse(code)

        cg = CallGraph()
        cg_builder = CallGraphBuilder(cg)
        cg_builder.extract_definitions(tree)

        cfg = self.builder.build(name, tree)
        cg_builder.build_from_cfg(cfg)
        return cg

    def test_direct_function_call(self):
        code = """
def foo():
    pass

def bar():
    foo()
    
bar()
"""
        cg = self._build_cg(code)

        # Nodes should exist
        self.assertTrue(cg.graph.has_node("foo"))
        self.assertTrue(cg.graph.has_node("bar"))
        self.assertTrue(cg.graph.has_node("test_module"))  # Global scope calls bar()

        # Edges
        self.assertTrue(cg.graph.has_edge("bar", "foo"))
        self.assertTrue(cg.graph.has_edge("test_module", "bar"))

    def test_speculative_method_call(self):
        code = """
class Dog:
    def speak(self):
        pass

class Cat:
    def speak(self):
        pass

def make_noise(animal):
    animal.speak()
"""
        cg = self._build_cg(code)

        # Check if classes are registered
        self.assertIn("Dog", cg.class_hierarchy)
        self.assertIn("Cat", cg.class_hierarchy)
        self.assertIn("speak", cg.class_hierarchy["Dog"])
        self.assertIn("speak", cg.class_hierarchy["Cat"])

        # Check speculative edges
        # make_noise calls animal.speak()
        # Should speculate edges to Dog.speak and Cat.speak

        self.assertTrue(cg.graph.has_edge("make_noise", "Dog.speak"))
        self.assertTrue(cg.graph.has_edge("make_noise", "Cat.speak"))

        edge_data = cg.graph.get_edge_data("make_noise", "Dog.speak")
        self.assertEqual(edge_data["type"], "speculative")

    def test_external_method_call(self):
        code = """
def process(data):
    data.unknown_method()
"""
        cg = self._build_cg(code)

        # Should have a generic node
        self.assertTrue(cg.graph.has_edge("process", "?.unknown_method"))
        self.assertTrue(cg.graph.has_node("?.unknown_method"))

        edge_data = cg.graph.get_edge_data("process", "?.unknown_method")
        self.assertEqual(edge_data["type"], "direct")  # Fallback to direct/generic

    def test_nested_function_scope(self):
        code = """
def outer():
    def inner():
        target()
    inner()

def target():
    pass
"""
        # Note: Current CFGBuilder implementation flatly visits FunctionDefs body when found.
        # It doesn't strictly enforce nested scopes in a way that 'inner' is a separate CFG scope
        # unless we explicitly handle it.
        # But our CFGBuilder logic:
        # visit_FunctionDef -> visits body.
        # Inner function definition is just a statement in outer.
        # Inner function body is visited when visit_FunctionDef is called for inner.
        # Let's see how our scope logic handles this.

        cg = self._build_cg(code)

        # Inner should call target
        self.assertTrue(cg.graph.has_edge("inner", "target"))

        # Outer should call inner (Wait, inner is defined but called? Yes, "inner()")
        self.assertTrue(cg.graph.has_edge("outer", "inner"))

    def test_speculative_expansion_limit(self):
        """
        Verify that speculative expansion honors the hard limit (MAX_SPECULATIVE_CANDIDATES).
        """
        # Create code with 7 classes implementing 'common'
        code = ""
        for char in "ABCDEFG":
            code += f"""
class {char}:
    def common(self): pass
"""
        code += """
def trigger(obj):
    obj.common()
"""
        cg = self._build_cg(code)

        # Verify limit
        limit = CallGraph.MAX_SPECULATIVE_CANDIDATES
        self.assertEqual(limit, 5)  # Default

        # Count edges from 'trigger'
        edges = [
            t
            for s, t, d in cg.graph.out_edges("trigger", data=True)
            if d.get("type") == "speculative"
        ]

        self.assertEqual(
            len(edges), limit, f"Expected {limit} speculative edges, found {len(edges)}"
        )

        # Verify that edges point to 'common' methods
        for target in edges:
            self.assertTrue(target.endswith(".common"))


if __name__ == "__main__":
    unittest.main()

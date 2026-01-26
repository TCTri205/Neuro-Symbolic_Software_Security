import ast
import unittest
import textwrap
from src.core.parser.preprocessing import strip_docstrings, strip_comments


class TestPreprocessing(unittest.TestCase):
    def test_strip_docstrings(self):
        source = textwrap.dedent("""
            '''Module docstring'''
            def foo():
                '''Function docstring'''
                pass
            
            class Bar:
                '''Class docstring'''
                def method(self):
                    "Method docstring"
                    x = 1
        """)
        tree = ast.parse(source)

        # Verify docstrings exist initially
        self.assertIsInstance(tree.body[0], ast.Expr)  # Module docstring

        # Strip
        strip_docstrings(tree)

        # Verify removal
        self.assertNotIsInstance(tree.body[0], ast.Expr)
        self.assertIsInstance(tree.body[0], ast.FunctionDef)  # foo

        func_foo = tree.body[0]
        self.assertIsInstance(func_foo.body[0], ast.Pass)  # No docstring

        class_bar = tree.body[1]
        self.assertNotIsInstance(class_bar.body[0], ast.Expr)  # No docstring

        method = class_bar.body[0]
        self.assertNotIsInstance(method.body[0], ast.Expr)  # No docstring
        self.assertIsInstance(method.body[0], ast.Assign)

    def test_strip_comments(self):
        source = textwrap.dedent("""
            x = 1 # Inline comment
            # Full line comment
            y = 2
            
            def foo():
                # Indented comment
                return 3
        """).strip()

        stripped = strip_comments(source)

        # Verify content
        self.assertIn("x = 1", stripped)
        self.assertNotIn("# Inline comment", stripped)
        self.assertNotIn("# Full line comment", stripped)
        self.assertIn("y = 2", stripped)

        # Verify line numbers (newlines preserved)
        original_lines = source.splitlines()
        stripped_lines = stripped.splitlines()
        self.assertEqual(len(original_lines), len(stripped_lines))

        # Check specific replacements
        self.assertTrue(
            stripped_lines[0].endswith("                 ")
        )  # Spaces for comment
        self.assertEqual(stripped_lines[1].strip(), "")  # Empty (spaces)

    def test_strip_comments_preserves_indentation(self):
        source = "    x = 1\n    # Comment\n    y = 2"
        stripped = strip_comments(source)

        lines = stripped.splitlines()
        self.assertEqual(lines[0], "    x = 1")
        self.assertEqual(lines[2], "    y = 2")
        # The comment line should be all spaces
        self.assertTrue(lines[1].isspace() or not lines[1])


if __name__ == "__main__":
    unittest.main()

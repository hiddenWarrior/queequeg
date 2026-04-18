import ast
import unittest
from harpoon.symbol_indexer import SymbolIndexer

FILE = "/test.py"


def index(source: str, file_path: str = FILE) -> dict:
    tree = ast.parse(source)
    return SymbolIndexer().index(source, tree, file_path)


class TestFunctions(unittest.TestCase):
    def test_top_level_function_indexed(self):
        symbols = index("def f(): pass")
        self.assertIn("f", symbols)

    def test_function_type(self):
        symbols = index("def f(): pass")
        self.assertEqual(symbols["f"]["type"], "function")

    def test_async_function_indexed(self):
        symbols = index("async def f(): pass")
        self.assertIn("f", symbols)

    def test_async_function_type(self):
        symbols = index("async def f(): pass")
        self.assertEqual(symbols["f"]["type"], "function")

    def test_function_file_path(self):
        symbols = index("def f(): pass")
        self.assertEqual(symbols["f"]["file_path"], FILE)

    def test_function_class_prefix_empty(self):
        symbols = index("def f(): pass")
        self.assertEqual(symbols["f"]["class_prefix"], "")

    def test_function_code_contains_def(self):
        symbols = index("def f(): pass")
        self.assertIn("def f():", symbols["f"]["code"])

    def test_function_node_is_ast_node(self):
        symbols = index("def f(): pass")
        self.assertIsInstance(symbols["f"]["node"], (ast.FunctionDef, ast.AsyncFunctionDef))

    def test_decorated_function_code_includes_decorator(self):
        symbols = index("@decorator\ndef f(): pass")
        self.assertIn("@decorator", symbols["f"]["code"])


class TestClasses(unittest.TestCase):
    def test_top_level_class_indexed(self):
        symbols = index("class Foo: pass")
        self.assertIn("Foo", symbols)

    def test_class_type(self):
        symbols = index("class Foo: pass")
        self.assertEqual(symbols["Foo"]["type"], "class")

    def test_class_file_path(self):
        symbols = index("class Foo: pass")
        self.assertEqual(symbols["Foo"]["file_path"], FILE)

    def test_class_prefix_empty(self):
        symbols = index("class Foo: pass")
        self.assertEqual(symbols["Foo"]["class_prefix"], "")

    def test_decorated_class_code_includes_decorator(self):
        symbols = index("@dataclass\nclass Foo: pass")
        self.assertIn("@dataclass", symbols["Foo"]["code"])


class TestVariables(unittest.TestCase):
    def test_assign_indexed(self):
        symbols = index("X = 1")
        self.assertIn("X", symbols)

    def test_assign_type(self):
        symbols = index("X = 1")
        self.assertEqual(symbols["X"]["type"], "variable")

    def test_annotated_assign_indexed(self):
        symbols = index("X: int = 1")
        self.assertIn("X", symbols)

    def test_annotated_assign_type(self):
        symbols = index("X: int = 1")
        self.assertEqual(symbols["X"]["type"], "variable")

    def test_multiple_assignment_targets_both_indexed(self):
        symbols = index("A = B = 1")
        self.assertIn("A", symbols)
        self.assertIn("B", symbols)

    def test_assign_inside_class_not_indexed_as_top_level(self):
        symbols = index("class Foo:\n    X = 1")
        self.assertNotIn("X", symbols)

    def test_annotated_assign_inside_class_not_indexed(self):
        symbols = index("class Foo:\n    x: int = 0")
        self.assertNotIn("x", symbols)


class TestMethods(unittest.TestCase):
    def test_method_indexed_with_class_prefix(self):
        symbols = index("class Foo:\n    def bar(self): pass")
        self.assertIn("Foo.bar", symbols)

    def test_method_type(self):
        symbols = index("class Foo:\n    def bar(self): pass")
        self.assertEqual(symbols["Foo.bar"]["type"], "function")

    def test_method_class_prefix(self):
        symbols = index("class Foo:\n    def bar(self): pass")
        self.assertEqual(symbols["Foo.bar"]["class_prefix"], "Foo.")

    def test_async_method_indexed(self):
        symbols = index("class Foo:\n    async def bar(self): pass")
        self.assertIn("Foo.bar", symbols)

    def test_multiple_methods_all_indexed(self):
        symbols = index("class Foo:\n    def a(self): pass\n    def b(self): pass")
        self.assertIn("Foo.a", symbols)
        self.assertIn("Foo.b", symbols)

    def test_class_and_method_both_present(self):
        symbols = index("class Foo:\n    def bar(self): pass")
        self.assertIn("Foo", symbols)
        self.assertIn("Foo.bar", symbols)


class TestNestedClasses(unittest.TestCase):
    def test_nested_class_indexed(self):
        symbols = index("class Outer:\n    class Inner:\n        pass")
        self.assertIn("Outer.Inner", symbols)

    def test_nested_class_type(self):
        symbols = index("class Outer:\n    class Inner:\n        pass")
        self.assertEqual(symbols["Outer.Inner"]["type"], "class")

    def test_nested_class_prefix(self):
        symbols = index("class Outer:\n    class Inner:\n        pass")
        self.assertEqual(symbols["Outer.Inner"]["class_prefix"], "Outer.")

    def test_method_on_nested_class_indexed(self):
        symbols = index(
            "class Outer:\n"
            "    class Inner:\n"
            "        def method(self): pass\n"
        )
        self.assertIn("Outer.Inner.method", symbols)

    def test_method_on_nested_class_prefix(self):
        symbols = index(
            "class Outer:\n"
            "    class Inner:\n"
            "        def method(self): pass\n"
        )
        self.assertEqual(symbols["Outer.Inner.method"]["class_prefix"], "Outer.Inner.")


class TestMultipleTopLevel(unittest.TestCase):
    def test_multiple_functions_all_indexed(self):
        symbols = index("def f(): pass\ndef g(): pass")
        self.assertIn("f", symbols)
        self.assertIn("g", symbols)

    def test_function_and_class_both_indexed(self):
        symbols = index("def f(): pass\nclass Foo: pass")
        self.assertIn("f", symbols)
        self.assertIn("Foo", symbols)

import ast
import unittest
from harpoon.class_reconstructor import ClassReconstructor
from harpoon.graph import Graph
from harpoon.ast_utils import get_source

FILE = "/test.py"


def build_cache(source: str, file_path: str = FILE) -> dict:
    """Build a minimal file_cache entry from source."""
    tree = ast.parse(source)
    symbols = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols[node.name] = {
                "node": node,
                "file_path": file_path,
                "type": "class",
                "code": get_source(source, node),
            }
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols[f"{node.name}.{child.name}"] = {
                        "node": child,
                        "file_path": file_path,
                        "type": "function",
                        "code": get_source(source, child),
                    }
                elif isinstance(child, ast.ClassDef):
                    symbols[f"{node.name}.{child.name}"] = {
                        "node": child,
                        "file_path": file_path,
                        "type": "class",
                        "code": get_source(source, child),
                    }
    return {"source": source, "symbols": symbols}


def make_graph(file_path: str, class_name: str, method_names: list) -> Graph:
    graph = Graph()
    class_id = f"{file_path}::{class_name}"
    graph.create_node(class_id, {"type": "class", "file_path": file_path, "name": class_name})
    for method in method_names:
        method_id = f"{file_path}::{class_name}.{method}"
        graph.create_node(method_id, {"type": "function", "file_path": file_path, "name": f"{class_name}.{method}"})
        graph.add_edge(class_id, method_id)
    return graph


class TestReconstructNoMethodNodes(unittest.TestCase):
    def test_class_with_no_method_nodes_code_unchanged(self):
        source = "class Foo:\n    def method(self): pass"
        cache = build_cache(source)
        graph = Graph()
        class_id = f"{FILE}::Foo"
        original_code = cache["symbols"]["Foo"]["code"]
        graph.create_node(class_id, {"type": "class", "file_path": FILE, "name": "Foo", "code": original_code})

        ClassReconstructor().reconstruct(graph, {FILE: cache})

        self.assertEqual(graph.get_node(class_id)["code"], original_code)

    def test_non_class_node_skipped(self):
        source = "def f(): pass"
        graph = Graph()
        node_id = f"{FILE}::f"
        graph.create_node(node_id, {"type": "function", "file_path": FILE, "name": "f", "code": "def f(): pass"})

        ClassReconstructor().reconstruct(graph, {})

        self.assertEqual(graph.get_node(node_id)["code"], "def f(): pass")

    def test_missing_file_path_in_cache_skipped(self):
        graph = Graph()
        class_id = f"{FILE}::Foo"
        graph.create_node(class_id, {"type": "class", "file_path": FILE, "name": "Foo", "code": "class Foo: pass"})

        ClassReconstructor().reconstruct(graph, {})  # empty cache

        self.assertEqual(graph.get_node(class_id)["code"], "class Foo: pass")


class TestReconstructSingleMethod(unittest.TestCase):
    def test_single_method_reconstructed(self):
        source = (
            "class Foo:\n"
            "    def run(self):\n"
            "        return 1\n"
        )
        cache = build_cache(source)
        graph = make_graph(FILE, "Foo", ["run"])

        ClassReconstructor().reconstruct(graph, {FILE: cache})

        code = graph.get_node(f"{FILE}::Foo")["code"]
        self.assertIn("class Foo:", code)
        self.assertIn("def run(self):", code)

    def test_method_not_in_graph_excluded(self):
        source = (
            "class Foo:\n"
            "    def run(self): pass\n"
            "    def helper(self): pass\n"
        )
        cache = build_cache(source)
        graph = make_graph(FILE, "Foo", ["run"])  # only run, not helper

        ClassReconstructor().reconstruct(graph, {FILE: cache})

        code = graph.get_node(f"{FILE}::Foo")["code"]
        self.assertIn("def run(self):", code)
        self.assertNotIn("def helper(self):", code)


class TestReconstructMultipleMethods(unittest.TestCase):
    def test_multiple_methods_all_included(self):
        source = (
            "class Foo:\n"
            "    def a(self): pass\n"
            "    def b(self): pass\n"
            "    def c(self): pass\n"
        )
        cache = build_cache(source)
        graph = make_graph(FILE, "Foo", ["a", "b", "c"])

        ClassReconstructor().reconstruct(graph, {FILE: cache})

        code = graph.get_node(f"{FILE}::Foo")["code"]
        self.assertIn("def a(self):", code)
        self.assertIn("def b(self):", code)
        self.assertIn("def c(self):", code)

    def test_methods_appear_in_source_order(self):
        source = (
            "class Foo:\n"
            "    def first(self): pass\n"
            "    def second(self): pass\n"
        )
        cache = build_cache(source)
        graph = make_graph(FILE, "Foo", ["first", "second"])

        ClassReconstructor().reconstruct(graph, {FILE: cache})

        code = graph.get_node(f"{FILE}::Foo")["code"]
        self.assertLess(code.index("def first"), code.index("def second"))


class TestReconstructClassAttributes(unittest.TestCase):
    def test_assign_attribute_always_included(self):
        source = (
            "class Foo:\n"
            "    x = 1\n"
            "    def run(self): pass\n"
        )
        cache = build_cache(source)
        graph = make_graph(FILE, "Foo", ["run"])

        ClassReconstructor().reconstruct(graph, {FILE: cache})

        code = graph.get_node(f"{FILE}::Foo")["code"]
        self.assertIn("x = 1", code)

    def test_annotated_attribute_always_included(self):
        source = (
            "class Foo:\n"
            "    x: int = 0\n"
            "    def run(self): pass\n"
        )
        cache = build_cache(source)
        graph = make_graph(FILE, "Foo", ["run"])

        ClassReconstructor().reconstruct(graph, {FILE: cache})

        code = graph.get_node(f"{FILE}::Foo")["code"]
        self.assertIn("x: int = 0", code)


class TestReconstructDecoratedClass(unittest.TestCase):
    def test_decorated_class_header_included(self):
        source = (
            "@dataclass\n"
            "class Foo:\n"
            "    def run(self): pass\n"
        )
        cache = build_cache(source)
        graph = make_graph(FILE, "Foo", ["run"])

        ClassReconstructor().reconstruct(graph, {FILE: cache})

        code = graph.get_node(f"{FILE}::Foo")["code"]
        self.assertIn("@dataclass", code)
        self.assertIn("class Foo:", code)


class TestReconstructNestedClass(unittest.TestCase):
    def test_nested_class_code_pulled_from_graph(self):
        source = (
            "class Outer:\n"
            "    class Inner:\n"
            "        def inner_method(self): pass\n"
            "    def outer_method(self): pass\n"
        )
        cache = build_cache(source)
        graph = Graph()
        outer_id = f"{FILE}::Outer"
        inner_id = f"{FILE}::Outer.Inner"
        outer_method_id = f"{FILE}::Outer.outer_method"

        graph.create_node(outer_id, {"type": "class", "file_path": FILE, "name": "Outer"})
        graph.create_node(inner_id, {"type": "class", "file_path": FILE, "name": "Outer.Inner", "code": "    class Inner:\n        def inner_method(self): pass"})
        graph.create_node(outer_method_id, {"type": "function", "file_path": FILE, "name": "Outer.outer_method"})
        graph.add_edge(outer_id, inner_id)
        graph.add_edge(outer_id, outer_method_id)

        ClassReconstructor().reconstruct(graph, {FILE: cache})

        code = graph.get_node(outer_id)["code"]
        self.assertIn("class Inner:", code)
        self.assertIn("def outer_method(self):", code)

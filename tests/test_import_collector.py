import ast
import os
import unittest
from harpoon.import_resolver import ImportResolver
from harpoon.import_collector import ImportCollector

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    return os.path.join(FIXTURES, name)


def make_func_node(code: str):
    """Parse a function definition and return its AST node."""
    return ast.parse(code).body[0]


def make_collector(fixture_name: str) -> ImportCollector:
    path = fixture(fixture_name)
    with open(path) as f:
        source = f.read()
    tree = ast.parse(source)
    return ImportCollector(ImportResolver(path, source, tree))


class TestInline(unittest.TestCase):
    def setUp(self):
        self.collector = make_collector("cross_file_a.py")

    def test_returns_import_from_function_body(self):
        func = make_func_node("""
def f():
    from tests.fixtures.cross_file_b import shared_helper
""")
        result = self.collector.inline(func)
        self.assertIn("shared_helper", result)

    def test_includes_imports_from_nested_function(self):
        func = make_func_node("""
def f():
    def inner():
        from tests.fixtures.cross_file_b import helper
""")
        result = self.collector.inline(func)
        self.assertIn("helper", result)

    def test_stdlib_excluded(self):
        func = make_func_node("""
def f():
    import os
""")
        result = self.collector.inline(func)
        self.assertEqual(result, {})

    def test_name_collision_last_write_wins(self):
        # flat dict — inner import overwrites outer under the same key
        func = make_func_node("""
def f():
    from tests.fixtures.cross_file_b import shared_helper as target
    def inner():
        from tests.fixtures.cross_file_b import helper as target
""")
        result = self.collector.inline(func)
        self.assertIn("target", result)
        self.assertEqual(len([k for k in result if k == "target"]), 1)


class TestDirect(unittest.TestCase):
    def setUp(self):
        self.collector = make_collector("cross_file_a.py")

    def test_returns_import_in_function_scope(self):
        func = make_func_node("""
def f():
    from tests.fixtures.cross_file_b import shared_helper
""")
        result = self.collector.direct(func)
        self.assertIn("shared_helper", result)

    def test_does_not_include_nested_function_imports(self):
        func = make_func_node("""
def f():
    def inner():
        from tests.fixtures.cross_file_b import helper
""")
        result = self.collector.direct(func)
        self.assertNotIn("helper", result)

    def test_stdlib_excluded(self):
        func = make_func_node("""
def f():
    import os
""")
        result = self.collector.direct(func)
        self.assertEqual(result, {})


class TestNestedDeps(unittest.TestCase):
    def setUp(self):
        self.collector = make_collector("cross_file_a.py")

    def test_returns_list_of_dep_pairs(self):
        func = make_func_node("""
def f():
    from tests.fixtures.cross_file_b import shared_helper
""")
        result = self.collector.nested_deps(func)
        self.assertIsInstance(result, list)

    def test_both_colliding_names_appear(self):
        # unlike inline(), nested_deps returns a list so both survive the collision
        func = make_func_node("""
def f():
    from tests.fixtures.cross_file_b import shared_helper as target
    def inner():
        from tests.fixtures.cross_file_b import helper as target
""")
        result = self.collector.nested_deps(func)
        dep_names = [dep_name for _, dep_name in result]
        self.assertIn("shared_helper", dep_names)
        self.assertIn("helper", dep_names)

    def test_whole_module_import_excluded(self):
        # dep_name is None for whole module imports — should not appear
        func = make_func_node("""
def f():
    import tests.fixtures.cross_file_b
""")
        result = self.collector.nested_deps(func)
        self.assertEqual(result, [])

    def test_stdlib_excluded(self):
        func = make_func_node("""
def f():
    import os
""")
        result = self.collector.nested_deps(func)
        self.assertEqual(result, [])


class TestDynamic(unittest.TestCase):
    def setUp(self):
        self.collector = make_collector("cross_file_a.py")

    def test_detects_importlib_import_module(self):
        func = make_func_node("""
def f():
    import importlib
    mod = importlib.import_module("tests.fixtures.cross_file_b")
""")
        result = self.collector.dynamic(func)
        self.assertIn("mod", result)

    def test_detects_bare_import_module(self):
        func = make_func_node("""
def f():
    mod = import_module("tests.fixtures.cross_file_b")
""")
        result = self.collector.dynamic(func)
        self.assertIn("mod", result)

    def test_non_project_module_excluded(self):
        func = make_func_node("""
def f():
    mod = importlib.import_module("os")
""")
        result = self.collector.dynamic(func)
        self.assertEqual(result, {})

    def test_non_literal_arg_excluded(self):
        func = make_func_node("""
def f():
    name = "tests.fixtures.cross_file_b"
    mod = importlib.import_module(name)
""")
        result = self.collector.dynamic(func)
        self.assertEqual(result, {})

import ast
import os
import unittest
from queequeg.import_resolver import ImportResolver

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    return os.path.join(FIXTURES, name)


def parse_import(code: str):
    """Parse a single import statement and return its AST node."""
    return ast.parse(code).body[0]


def make_resolver(fixture_name: str) -> ImportResolver:
    path = fixture(fixture_name)
    with open(path) as f:
        source = f.read()
    tree = ast.parse(source)
    return ImportResolver(path, source, tree)


class TestResolveFromImport(unittest.TestCase):
    def setUp(self):
        self.resolver = make_resolver("cross_file_a.py")

    def test_project_module_name_resolves(self):
        node = parse_import("from tests.fixtures.cross_file_b import shared_helper")
        result = self.resolver.resolve(node)
        self.assertIn("shared_helper", result)

    def test_resolved_file_path_is_correct(self):
        node = parse_import("from tests.fixtures.cross_file_b import shared_helper")
        result = self.resolver.resolve(node)
        self.assertIn("cross_file_b.py", result["shared_helper"][0])

    def test_resolved_name_is_original(self):
        node = parse_import("from tests.fixtures.cross_file_b import shared_helper")
        result = self.resolver.resolve(node)
        dep_file, dep_name, lineno = result["shared_helper"]
        self.assertEqual(dep_name, "shared_helper")

    def test_alias_is_used_as_local_name(self):
        node = parse_import("from tests.fixtures.cross_file_b import shared_helper as sh")
        result = self.resolver.resolve(node)
        self.assertIn("sh", result)
        self.assertNotIn("shared_helper", result)

    def test_alias_still_resolves_to_original_name(self):
        node = parse_import("from tests.fixtures.cross_file_b import shared_helper as sh")
        result = self.resolver.resolve(node)
        dep_file, dep_name, lineno = result["sh"]
        self.assertEqual(dep_name, "shared_helper")

    def test_stdlib_import_returns_empty(self):
        node = parse_import("from os.path import join")
        result = self.resolver.resolve(node)
        self.assertEqual(result, {})

    def test_nonexistent_module_returns_empty(self):
        node = parse_import("from nonexistent_xyz import something")
        result = self.resolver.resolve(node)
        self.assertEqual(result, {})

    def test_multiple_names_from_same_module(self):
        node = parse_import("from tests.fixtures.cross_file_b import shared_helper, helper")
        result = self.resolver.resolve(node)
        self.assertIn("shared_helper", result)
        self.assertIn("helper", result)


class TestResolveDirectImport(unittest.TestCase):
    def setUp(self):
        self.resolver = make_resolver("cross_file_a.py")

    def test_project_module_resolves(self):
        node = parse_import("import tests.fixtures.cross_file_b")
        result = self.resolver.resolve(node)
        self.assertIn("tests.fixtures.cross_file_b", result)

    def test_whole_module_dep_name_is_none(self):
        node = parse_import("import tests.fixtures.cross_file_b")
        result = self.resolver.resolve(node)
        dep_file, dep_name, lineno = result["tests.fixtures.cross_file_b"]
        self.assertIsNone(dep_name)

    def test_alias_used_as_local_name(self):
        node = parse_import("import tests.fixtures.cross_file_b as cfb")
        result = self.resolver.resolve(node)
        self.assertIn("cfb", result)
        self.assertNotIn("tests.fixtures.cross_file_b", result)

    def test_stdlib_module_returns_empty(self):
        node = parse_import("import os")
        result = self.resolver.resolve(node)
        self.assertEqual(result, {})


class TestResolveRelativeImport(unittest.TestCase):
    def setUp(self):
        self.resolver = make_resolver("relpkg/user.py")

    def test_relative_from_import_resolves(self):
        node = parse_import("from .utils import util_func")
        result = self.resolver.resolve(node)
        self.assertIn("util_func", result)

    def test_relative_from_import_file_path(self):
        node = parse_import("from .utils import util_func")
        result = self.resolver.resolve(node)
        dep_file, dep_name, lineno = result["util_func"]
        self.assertIn("utils.py", dep_file)

    def test_relative_submodule_import(self):
        node = parse_import("from . import utils")
        result = self.resolver.resolve(node)
        self.assertIn("utils", result)


class TestResolveStarImport(unittest.TestCase):
    def setUp(self):
        self.resolver = make_resolver("star_all_import.py")

    def test_star_import_expands_to_individual_names(self):
        node = parse_import("from tests.fixtures.star_all_source import *")
        result = self.resolver.resolve(node)
        self.assertIn("exported_func", result)

    def test_star_import_excludes_private_names(self):
        node = parse_import("from tests.fixtures.star_all_source import *")
        result = self.resolver.resolve(node)
        for name in result:
            self.assertFalse(name.startswith("_"))

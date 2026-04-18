import ast
import os
import unittest
from harpoon.tracer import Tracer
from harpoon.graph import Graph

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    return os.path.join(FIXTURES, name)


def node_names(graph):
    return {n.split("::")[-1] for n in graph.nodes()}


def run_trace(file_path, name):
    graph = Graph()
    tracer = Tracer()
    tracer.trace(os.path.abspath(file_path), name, graph, visited=set())
    return graph, tracer


class TestLoad(unittest.TestCase):
    def test_returns_source_string(self):
        source, _ = Tracer().load(fixture("simple.py"))
        self.assertIsInstance(source, str)
        self.assertIn("def standalone", source)

    def test_returns_parsed_tree(self):
        _, tree = Tracer().load(fixture("simple.py"))
        self.assertIsInstance(tree, ast.Module)

    def test_tree_has_body(self):
        _, tree = Tracer().load(fixture("simple.py"))
        self.assertTrue(len(tree.body) > 0)


class TestTraceNodeCreation(unittest.TestCase):
    def test_creates_node_for_traced_symbol(self):
        graph, _ = run_trace(fixture("simple.py"), "standalone")
        self.assertIn("standalone", node_names(graph))

    def test_node_has_code(self):
        graph, _ = run_trace(fixture("simple.py"), "standalone")
        node_id = next(n for n in graph.nodes() if n.endswith("::standalone"))
        self.assertIn("def standalone", graph.get_node(node_id)["code"])

    def test_node_has_type(self):
        graph, _ = run_trace(fixture("simple.py"), "standalone")
        node_id = next(n for n in graph.nodes() if n.endswith("::standalone"))
        self.assertEqual(graph.get_node(node_id)["type"], "function")

    def test_node_has_file_path(self):
        graph, _ = run_trace(fixture("simple.py"), "standalone")
        node_id = next(n for n in graph.nodes() if n.endswith("::standalone"))
        self.assertTrue(graph.get_node(node_id)["file_path"].endswith("simple.py"))

    def test_node_has_name(self):
        graph, _ = run_trace(fixture("simple.py"), "standalone")
        node_id = next(n for n in graph.nodes() if n.endswith("::standalone"))
        self.assertEqual(graph.get_node(node_id)["name"], "standalone")


class TestTraceDependencies(unittest.TestCase):
    def test_follows_local_dependency(self):
        graph, _ = run_trace(fixture("simple.py"), "uses_helper")
        self.assertIn("helper", node_names(graph))

    def test_follows_global_variable_dependency(self):
        graph, _ = run_trace(fixture("simple.py"), "uses_global")
        self.assertIn("MAX_SIZE", node_names(graph))

    def test_standalone_has_no_deps(self):
        graph, _ = run_trace(fixture("simple.py"), "standalone")
        self.assertEqual(node_names(graph), {"standalone"})

    def test_follows_cross_file_dependency(self):
        graph, _ = run_trace(fixture("cross_file_a.py"), "uses_imported_function")
        names = node_names(graph)
        self.assertIn("shared_helper", names)


class TestTraceVisited(unittest.TestCase):
    def test_visited_prevents_revisit(self):
        file_path = os.path.abspath(fixture("simple.py"))
        graph = Graph()
        tracer = Tracer()
        visited = set()
        tracer.trace(file_path, "uses_helper", graph, visited)
        node_count_after_first = len(graph.nodes())
        tracer.trace(file_path, "uses_helper", graph, visited)
        self.assertEqual(len(graph.nodes()), node_count_after_first)

    def test_file_cache_populated_after_trace(self):
        file_path = os.path.abspath(fixture("simple.py"))
        _, tracer = run_trace(fixture("simple.py"), "standalone")
        self.assertIn(file_path, tracer.file_cache)

    def test_file_cache_has_expected_keys(self):
        file_path = os.path.abspath(fixture("simple.py"))
        _, tracer = run_trace(fixture("simple.py"), "standalone")
        cache = tracer.file_cache[file_path]
        self.assertIn("source", cache)
        self.assertIn("tree", cache)
        self.assertIn("symbols", cache)
        self.assertIn("import_map", cache)
        self.assertIn("collector", cache)


class TestTraceMissingSymbol(unittest.TestCase):
    def test_missing_name_logs_warning_and_skips(self):
        file_path = os.path.abspath(fixture("simple.py"))
        graph = Graph()
        tracer = Tracer()
        # force file into cache first, then request nonexistent symbol
        tracer.trace(file_path, "standalone", graph, visited=set())
        before = len(graph.nodes())
        tracer.trace(file_path, "nonexistent", graph, visited=set())
        self.assertEqual(len(graph.nodes()), before)


class TestTraceNoDeps(unittest.TestCase):
    def test_trace_deps_false_skips_dep_collection(self):
        file_path = os.path.abspath(fixture("simple.py"))
        graph = Graph()
        tracer = Tracer()
        tracer.trace(file_path, "uses_helper", graph, visited=set(), trace_deps=False)
        self.assertIn("uses_helper", node_names(graph))
        self.assertNotIn("helper", node_names(graph))


class TestTraceParentClass(unittest.TestCase):
    def test_method_trace_adds_parent_class_node(self):
        graph, _ = run_trace(fixture("classes.py"), "Animal.speak")
        self.assertIn("Animal", node_names(graph))

    def test_parent_class_added_without_tracing_its_deps(self):
        graph, _ = run_trace(fixture("classes.py"), "Animal.speak")
        # Animal.sleep should NOT be in graph — it's not a dep of speak
        self.assertNotIn("Animal.sleep", node_names(graph))


class TestPropagateToAncestors(unittest.TestCase):
    def test_ancestor_gets_edge_to_external_dep(self):
        file_path = os.path.abspath(fixture("classes.py"))
        graph = Graph()
        tracer = Tracer()
        tracer.trace(file_path, "Animal.speak", graph, visited=set())

        helper_id = f"{file_path}::helper"
        animal_id = f"{file_path}::Animal"
        self.assertIn(helper_id, graph.neighbors(animal_id))

    def test_own_method_not_propagated_to_ancestor(self):
        file_path = os.path.abspath(fixture("classes.py"))
        graph = Graph()
        tracer = Tracer()
        tracer.trace(file_path, "Dog.fetch", graph, visited=set())

        dog_id = f"{file_path}::Dog"
        speak_id = f"{file_path}::Dog.speak"
        self.assertNotIn(speak_id, graph.neighbors(dog_id))

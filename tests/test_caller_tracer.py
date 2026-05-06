import os
import unittest
from queequeg.parser import Parser

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    return os.path.join(FIXTURES, name)


def node_names(graph):
    return {n.split("::")[-1] for n in graph.nodes()}


def run_trace_callers(file_path, name):
    return Parser().trace_callers(file_path, name, search_path=FIXTURES)


class TestTargetInGraph(unittest.TestCase):
    def test_target_itself_is_in_graph(self):
        graph = run_trace_callers(fixture("callee.py"), "callee_func")
        self.assertIn("callee_func", node_names(graph))


class TestDirectCallers(unittest.TestCase):
    def test_direct_caller_found(self):
        graph = run_trace_callers(fixture("callee.py"), "callee_func")
        self.assertIn("calls_callee", node_names(graph))

    def test_non_caller_not_in_graph(self):
        graph = run_trace_callers(fixture("callee.py"), "callee_func")
        self.assertNotIn("does_not_call_callee", node_names(graph))

    def test_unrelated_func_not_in_graph(self):
        graph = run_trace_callers(fixture("callee.py"), "callee_func")
        self.assertNotIn("unrelated_func", node_names(graph))


class TestTransitiveCallers(unittest.TestCase):
    def test_transitive_caller_found(self):
        graph = run_trace_callers(fixture("callee.py"), "callee_func")
        self.assertIn("calls_direct_caller", node_names(graph))


class TestEdgeDirection(unittest.TestCase):
    def test_caller_has_edge_to_target(self):
        graph = run_trace_callers(fixture("callee.py"), "callee_func")
        caller_id = next(n for n in graph.nodes() if n.endswith("::calls_callee"))
        target_id = next(n for n in graph.nodes() if n.endswith("::callee_func"))
        self.assertIn(target_id, graph.neighbors(caller_id))


class TestNoCallers(unittest.TestCase):
    def test_function_with_no_callers_returns_only_itself(self):
        graph = run_trace_callers(fixture("callee.py"), "unrelated_func")
        self.assertEqual(node_names(graph), {"unrelated_func"})


class TestErrorHandling(unittest.TestCase):
    def test_nonexistent_symbol_raises(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            run_trace_callers(fixture("callee.py"), "nonexistent")


if __name__ == "__main__":
    unittest.main()

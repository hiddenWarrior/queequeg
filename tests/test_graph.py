import unittest
from harpoon.graph import Graph


class TestCreateNode(unittest.TestCase):
    def test_create_node(self):
        g = Graph()
        g.create_node("a")
        self.assertIn("a", g.nodes())

    def test_create_node_with_metadata(self):
        g = Graph()
        g.create_node("a", {"type": "function"})
        self.assertEqual(g.get_node("a")["type"], "function")

    def test_create_node_updates_existing_metadata(self):
        g = Graph()
        g.create_node("a", {"type": "function"})
        g.create_node("a", {"type": "class"})
        self.assertEqual(g.get_node("a")["type"], "class")

    def test_create_node_does_not_duplicate(self):
        g = Graph()
        g.create_node("a")
        g.create_node("a")
        self.assertEqual(len(g.nodes()), 1)


class TestAddEdge(unittest.TestCase):
    def test_add_edge_creates_connection(self):
        g = Graph()
        g.create_node("a")
        g.create_node("b")
        g.add_edge("a", "b")
        self.assertIn("b", g.neighbors("a"))

    def test_add_edge_creates_nodes_if_missing(self):
        g = Graph()
        g.add_edge("a", "b")
        self.assertIn("a", g.nodes())
        self.assertIn("b", g.nodes())


class TestDetectCycles(unittest.TestCase):
    def test_no_cycles(self):
        g = Graph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        self.assertEqual(g.detect_cycles(), [])

    def test_detects_cycle(self):
        g = Graph()
        g.add_edge("a", "b")
        g.add_edge("b", "a")
        self.assertTrue(len(g.detect_cycles()) > 0)


class TestTopologicalSort(unittest.TestCase):
    def test_dependency_comes_before_dependent(self):
        g = Graph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        order = g.topological_sort()
        self.assertLess(order.index("a"), order.index("b"))
        self.assertLess(order.index("b"), order.index("c"))

    def test_handles_cycle_without_crash(self):
        g = Graph()
        g.add_edge("a", "b")
        g.add_edge("b", "a")
        result = g.topological_sort()
        self.assertIn("a", result)
        self.assertIn("b", result)


class TestTraverse(unittest.TestCase):
    def test_traverse_returns_reachable_nodes(self):
        g = Graph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.create_node("d")
        result = g.traverse("a")
        self.assertIn("a", result)
        self.assertIn("b", result)
        self.assertIn("c", result)
        self.assertNotIn("d", result)

    def test_traverse_unknown_node_raises(self):
        g = Graph()
        with self.assertRaises(ValueError):
            g.traverse("unknown")


class TestNeighbors(unittest.TestCase):
    def test_neighbors_returns_direct_dependencies(self):
        g = Graph()
        g.add_edge("a", "b")
        g.add_edge("a", "c")
        self.assertEqual(set(g.neighbors("a")), {"b", "c"})

    def test_neighbors_no_edges(self):
        g = Graph()
        g.create_node("a")
        self.assertEqual(g.neighbors("a"), [])


class TestHasNode(unittest.TestCase):
    def test_has_node_true(self):
        g = Graph()
        g.create_node("a")
        self.assertTrue(g.has_node("a"))

    def test_has_node_false(self):
        g = Graph()
        self.assertFalse(g.has_node("nonexistent"))

    def test_has_node_after_edge_creation(self):
        g = Graph()
        g.add_edge("a", "b")
        self.assertTrue(g.has_node("a"))
        self.assertTrue(g.has_node("b"))


class TestGetNode(unittest.TestCase):
    def test_get_node_returns_metadata(self):
        g = Graph()
        g.create_node("a", {"type": "function", "file_path": "/foo.py"})
        node = g.get_node("a")
        self.assertEqual(node["type"], "function")
        self.assertEqual(node["file_path"], "/foo.py")

    def test_get_node_empty_metadata(self):
        g = Graph()
        g.create_node("a")
        self.assertEqual(g.get_node("a"), {})


class TestEmptyGraph(unittest.TestCase):
    def test_nodes_empty(self):
        g = Graph()
        self.assertEqual(g.nodes(), [])

    def test_topological_sort_empty(self):
        g = Graph()
        self.assertEqual(g.topological_sort(), [])

    def test_detect_cycles_empty(self):
        g = Graph()
        self.assertEqual(g.detect_cycles(), [])


class TestTopologicalSortDisconnected(unittest.TestCase):
    def test_disconnected_subgraphs_all_present(self):
        g = Graph()
        g.add_edge("a", "b")
        g.add_edge("c", "d")
        order = g.topological_sort()
        self.assertEqual(set(order), {"a", "b", "c", "d"})
        self.assertLess(order.index("a"), order.index("b"))
        self.assertLess(order.index("c"), order.index("d"))

    def test_isolated_node_included(self):
        g = Graph()
        g.add_edge("a", "b")
        g.create_node("z")
        order = g.topological_sort()
        self.assertIn("z", order)


if __name__ == "__main__":
    unittest.main()

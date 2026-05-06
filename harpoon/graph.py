import logging
import networkx as nx

logger = logging.getLogger(__name__)


class Graph:
    def __init__(self):
        self._graph = nx.DiGraph()

    def create_node(self, name: str, metadata: dict = None):
        if self._graph.has_node(name):
            self._graph.nodes[name].update(metadata or {})
        else:
            self._graph.add_node(name, **(metadata or {}))

    def add_edge(self, from_node: str, to_node: str):
        self._graph.add_edge(from_node, to_node)

    def detect_cycles(self) -> list:
        cycles = list(nx.simple_cycles(self._graph))
        if cycles:
            logger.warning(f"Circular dependencies detected: {cycles}")
        return cycles

    def topological_sort(self) -> list:
        self.detect_cycles()
        try:
            return list(nx.topological_sort(self._graph))
        except nx.NetworkXUnfeasible:
            logger.warning("Topological sort not possible due to cycles, returning best effort order")
            return list(self._graph.nodes)

    def traverse(self, start_node: str) -> list:
        if not self._graph.has_node(start_node):
            raise ValueError(f"Node '{start_node}' not found in graph")
        return list(nx.dfs_preorder_nodes(self._graph, start_node))

    def get_node(self, name: str) -> dict:
        return self._graph.nodes[name]

    def nodes(self) -> list:
        return list(self._graph.nodes)

    def neighbors(self, name: str) -> list:
        return list(self._graph.successors(name))

    def predecessors(self, name: str) -> list:
        return list(self._graph.predecessors(name))

    def has_node(self, name: str) -> bool:
        return self._graph.has_node(name)

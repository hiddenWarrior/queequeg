import json
import os
from ..graph import Graph


def _rel_node_id(node_id: str) -> str:
    if "::" in node_id:
        path, name = node_id.split("::", 1)
        return f"{os.path.relpath(path)}::{name}"
    return node_id


class CallersSerializer:
    def translate(self, graph: Graph) -> str:
        nodes = {}
        for node_id in graph.nodes():
            node = graph.get_node(node_id)
            file_path = node.get("file_path")
            callers = [_rel_node_id(c) for c in graph.predecessors(node_id)]
            nodes[_rel_node_id(node_id)] = {
                "type": node.get("type"),
                "file_path": os.path.relpath(file_path) if file_path else None,
                "callers": callers,
            }
        return json.dumps(nodes, indent=2)

import os
from ..graph import Graph


class CodeSerializer:
    def translate(self, graph: Graph) -> str:
        ordered = graph.topological_sort()
        all_names = {
            graph.get_node(n).get("name", n.split("::")[-1])
            for n in graph.nodes()
        }

        chunks = []
        for node_id in reversed(ordered):
            node = graph.get_node(node_id)
            if not node.get("code"):
                continue
            name = node.get("name", node_id.split("::")[-1])

            # Skip if parent class is in the graph — it will be included in class reconstruction
            if "." in name:
                parent = ".".join(name.split(".")[:-1])
                if parent in all_names:
                    continue

            rel_path = os.path.relpath(node["file_path"])
            file_comment = f"# file: {rel_path}"
            chunks.append(f"{file_comment}\n{node['code']}")

        return "\n\n".join(chunks)

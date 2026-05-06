import os
from ..graph import Graph


class CodeSerializer:
    def translate(self, graph: Graph) -> str:
        ordered = graph.topological_sort()
        all_names = {
            graph.get_node(n).get("name", n.split("::")[-1])
            for n in graph.nodes()
        }

        # Collect (rel_path, code) in topological order (reversed = leaves first)
        entries = []
        for node_id in reversed(ordered):
            node = graph.get_node(node_id)
            if not node.get("code"):
                continue
            name = node.get("name", node_id.split("::")[-1])

            # Skip if parent class is in the graph — included in class reconstruction
            if "." in name:
                parent = ".".join(name.split(".")[:-1])
                if parent in all_names:
                    continue

            rel_path = os.path.relpath(node["file_path"])
            entries.append((rel_path, node["code"]))

        # Group by file while preserving first-appearance order (topological)
        file_order = []
        file_codes = {}
        for rel_path, code in entries:
            if rel_path not in file_codes:
                file_order.append(rel_path)
                file_codes[rel_path] = []
            file_codes[rel_path].append(code)

        # One # file: header per file section; symbols separated by \n\n\n
        sections = []
        for rel_path in file_order:
            codes = file_codes[rel_path]
            section = f"# file: {rel_path}\n" + "\n\n\n".join(codes)
            sections.append(section)

        return "\n\n\n".join(sections)

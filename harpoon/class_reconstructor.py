import ast
from .graph import Graph
from .ast_utils import get_source


class ClassReconstructor:
    def reconstruct(self, graph: Graph, file_cache: dict):
        for node_id in graph.topological_sort():
            node = graph.get_node(node_id)
            if node.get("type") != "class":
                continue
            name = node.get("name", node_id.split("::")[-1])
            file_path = node["file_path"]
            if file_path not in file_cache:
                continue
            symbols = file_cache[file_path]["symbols"]
            class_node = symbols.get(name, {}).get("node")
            if class_node is None:
                continue

            has_method_nodes = any(
                graph.has_node(f"{file_path}::{name}.{m.name}")
                for m in class_node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            )
            if has_method_nodes:
                reconstructed = self._reconstruct_class_code(name, file_path, graph, file_cache)
                graph.create_node(node_id, {"code": reconstructed})

    def _reconstruct_class_code(self, class_name: str, file_path: str, graph: Graph, file_cache: dict) -> str:
        source = file_cache[file_path]["source"]
        symbols = file_cache[file_path]["symbols"]
        class_node = symbols[class_name]["node"]
        lines = source.splitlines()

        if class_node.decorator_list:
            header_start = class_node.decorator_list[0].lineno - 1
        else:
            header_start = class_node.lineno - 1
        header_end = class_node.body[0].lineno - 1
        header = "\n".join(lines[header_start:header_end])

        parts = []
        for node in class_node.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_name = f"{class_name}.{node.name}"
                if graph.has_node(f"{file_path}::{method_name}"):
                    parts.append(get_source(source, node))
            elif isinstance(node, ast.ClassDef):
                nested_name = f"{class_name}.{node.name}"
                nested_id = f"{file_path}::{nested_name}"
                if graph.has_node(nested_id):
                    parts.append(graph.get_node(nested_id)["code"])
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                parts.append(get_source(source, node))

        return header + "\n" + "\n\n".join(parts)

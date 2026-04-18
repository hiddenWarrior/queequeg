import ast
import os
import logging
from .graph import Graph
from .import_resolver import ImportResolver
from .import_collector import ImportCollector
from .ast_utils import walk_current_scope, get_source
from .dependency_extractor import DependencyExtractor
from .class_reconstructor import ClassReconstructor

logger = logging.getLogger(__name__)


class Parser:
    def _load(self, file_path: str) -> tuple:
        with open(file_path) as f:
            source = f.read()
        tree = ast.parse(source)
        return source, tree

    def _index_body(self, source: str, body, file_path: str, symbols: dict, prefix: str = ""):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{node.name}"
                symbols[name] = {
                    "node": node,
                    "code": get_source(source, node),
                    "type": "function",
                    "file_path": file_path,
                    "class_prefix": prefix,
                }
            elif isinstance(node, ast.ClassDef):
                name = f"{prefix}{node.name}"
                symbols[name] = {
                    "node": node,
                    "code": get_source(source, node),
                    "type": "class",
                    "file_path": file_path,
                    "class_prefix": prefix,
                }
                self._index_body(source, node.body, file_path, symbols, prefix=f"{name}.")
            elif isinstance(node, ast.Assign) and not prefix:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols[target.id] = {
                            "node": node,
                            "code": get_source(source, node),
                            "type": "variable",
                            "file_path": file_path,
                            "class_prefix": "",
                        }
            elif isinstance(node, ast.AnnAssign) and not prefix:
                if isinstance(node.target, ast.Name):
                    symbols[node.target.id] = {
                        "node": node,
                        "code": get_source(source, node),
                        "type": "variable",
                        "file_path": file_path,
                        "class_prefix": "",
                    }

    def _index_symbols(self, source: str, tree, file_path: str) -> dict:
        symbols = {}
        self._index_body(source, tree.body, file_path, symbols)
        return symbols


    def trace(self, file_path: str, name: str) -> Graph:
        file_path = os.path.abspath(file_path)
        source, tree = self._load(file_path)
        symbols = self._index_symbols(source, tree, file_path)

        if name not in symbols:
            raise ValueError(f"'{name}' not found in '{file_path}'")

        graph = Graph()
        file_cache = {}
        self._trace_recursive(file_path, name, graph, visited=set(), file_cache=file_cache)
        ClassReconstructor().reconstruct(graph, file_cache)
        return graph

    def _trace_recursive(self, file_path: str, name: str, graph: Graph, visited: set, file_cache: dict, trace_deps: bool = True):
        if (file_path, name) in visited:
            return
        visited.add((file_path, name))

        if file_path not in file_cache:
            source, tree = self._load(file_path)
            resolver = ImportResolver(file_path, source, tree)
            file_cache[file_path] = {
                "source": source,
                "tree": tree,
                "symbols": self._index_symbols(source, tree, file_path),
                "import_map": resolver._build_import_map(tree),
                "collector": ImportCollector(resolver),
            }

        symbols = file_cache[file_path]["symbols"]
        import_map = file_cache[file_path]["import_map"]

        if name not in symbols:
            logger.warning(f"'{name}' not found in '{file_path}', skipping")
            return

        symbol = symbols[name]
        node_id = f"{file_path}::{name}"
        graph.create_node(node_id, {
            "code": symbol["code"],
            "type": symbol["type"],
            "file_path": file_path,
            "name": name,
        })

        # If this is a method or nested class, add parent class as a node (no dep tracing)
        parts = name.rsplit(".", 1)
        if len(parts) > 1:
            parent_name = parts[0]
            if parent_name in symbols:
                parent_id = f"{file_path}::{parent_name}"
                graph.add_edge(node_id, parent_id)
                self._trace_recursive(file_path, parent_name, graph, visited, file_cache, trace_deps=False)

        if not trace_deps:
            return

        collector = file_cache[file_path]["collector"]
        all_inline = collector.inline(symbol["node"])
        direct_inline = collector.direct(symbol["node"])
        dynamic_imports = collector.dynamic(symbol["node"])
        nested_deps = collector.nested_deps(symbol["node"])
        effective_import_map = {**all_inline, **import_map, **direct_inline, **dynamic_imports}
        deps, constructor_import_set = DependencyExtractor(symbols, effective_import_map, name, dynamic_imports=dynamic_imports).extract(symbol["node"])
        deps += nested_deps

        # Propagate external deps up the ancestor chain for correct topological ordering
        self._propagate_deps_to_ancestors(name, file_path, deps, symbols, graph)

        for dep_file, dep_name in deps:
            dep_id = f"{dep_file}::{dep_name}"
            graph.add_edge(node_id, dep_id)
            self._trace_recursive(dep_file, dep_name, graph, visited, file_cache)
            if (dep_file, dep_name) in constructor_import_set:
                if dep_file in file_cache:
                    init_name = f"{dep_name}.__init__"
                    if init_name in file_cache[dep_file]["symbols"]:
                        init_id = f"{dep_file}::{init_name}"
                        graph.add_edge(node_id, init_id)
                        self._trace_recursive(dep_file, init_name, graph, visited, file_cache)

    def _propagate_deps_to_ancestors(self, name: str, file_path: str, deps: list, symbols: dict, graph: Graph):
        """Add edges from each ancestor class to external deps so ordering is correct."""
        name_parts = name.split(".")
        for i in range(len(name_parts) - 1, 0, -1):
            ancestor_name = ".".join(name_parts[:i])
            if ancestor_name not in symbols:
                break
            ancestor_id = f"{file_path}::{ancestor_name}"
            for dep_file, dep_name in deps:
                if dep_file == file_path and dep_name.startswith(ancestor_name + "."):
                    continue
                dep_id = f"{dep_file}::{dep_name}"
                graph.add_edge(ancestor_id, dep_id)

import ast
import logging
import os
from .graph import Graph
from .import_resolver import ImportResolver
from .import_collector import ImportCollector
from .dependency_extractor import DependencyExtractor
from .symbol_indexer import SymbolIndexer

logger = logging.getLogger(__name__)


class Tracer:
    def __init__(self):
        self._indexer = SymbolIndexer()
        self.file_cache: dict = {}

    def load(self, file_path: str) -> tuple:
        with open(file_path) as f:
            source = f.read()
        tree = ast.parse(source)
        return source, tree

    def trace(self, file_path: str, name: str, graph: Graph, visited: set, trace_deps: bool = True):
        if (file_path, name) in visited:
            return
        visited.add((file_path, name))

        if file_path not in self.file_cache:
            source, tree = self.load(file_path)
            resolver = ImportResolver(file_path, source, tree)
            self.file_cache[file_path] = {
                "source": source,
                "tree": tree,
                "symbols": self._indexer.index(source, tree, file_path),
                "import_map": resolver._build_import_map(tree),
                "collector": ImportCollector(resolver),
            }

        symbols = self.file_cache[file_path]["symbols"]
        import_map = self.file_cache[file_path]["import_map"]

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
                self.trace(file_path, parent_name, graph, visited, trace_deps=False)

        if not trace_deps:
            return

        collector = self.file_cache[file_path]["collector"]
        all_inline = collector.inline(symbol["node"])
        direct_inline = collector.direct(symbol["node"])
        dynamic_imports = collector.dynamic(symbol["node"])
        nested_deps = collector.nested_deps(symbol["node"])
        effective_import_map = {**all_inline, **import_map, **direct_inline, **dynamic_imports}
        deps, constructor_import_set = DependencyExtractor(symbols, effective_import_map, name, dynamic_imports=dynamic_imports).extract(symbol["node"])
        deps += nested_deps

        self._propagate_deps_to_ancestors(name, file_path, deps, symbols, graph)

        for dep_file, dep_name in deps:
            dep_id = f"{dep_file}::{dep_name}"
            graph.add_edge(node_id, dep_id)
            self.trace(dep_file, dep_name, graph, visited)
            if (dep_file, dep_name) in constructor_import_set:
                if dep_file in self.file_cache:
                    init_name = f"{dep_name}.__init__"
                    if init_name in self.file_cache[dep_file]["symbols"]:
                        init_id = f"{dep_file}::{init_name}"
                        graph.add_edge(node_id, init_id)
                        self.trace(dep_file, init_name, graph, visited)

    def _propagate_deps_to_ancestors(self, name: str, file_path: str, deps: list, symbols: dict, graph: Graph):
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

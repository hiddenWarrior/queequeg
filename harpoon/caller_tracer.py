import ast
import os
import logging
from .graph import Graph
from .symbol_indexer import SymbolIndexer
from .import_resolver import ImportResolver
from .import_collector import ImportCollector
from .dependency_extractor import DependencyExtractor

logger = logging.getLogger(__name__)

_SKIP_DIRS = {
    '.venv', 'venv', 'env', '__pycache__', '.git',
    'node_modules', 'dist', 'build', '.tox', '.eggs',
    '.mypy_cache', '.pytest_cache',
}


def _scan_python_files(search_path: str) -> list:
    result = []
    for dirpath, dirnames, filenames in os.walk(search_path):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith('.')]
        for filename in filenames:
            if filename.endswith('.py'):
                result.append(os.path.join(dirpath, filename))
    return result


class CallerTracer:
    def __init__(self):
        self._indexer = SymbolIndexer()
        self.file_cache: dict = {}

    def _load_file(self, file_path: str):
        if file_path in self.file_cache:
            return
        try:
            with open(file_path) as f:
                source = f.read()
            tree = ast.parse(source)
            resolver = ImportResolver(file_path, source, tree)
            self.file_cache[file_path] = {
                "source": source,
                "tree": tree,
                "symbols": self._indexer.index(source, tree, file_path),
                "import_map": resolver._build_import_map(tree),
                "collector": ImportCollector(resolver),
            }
        except Exception as e:
            logger.debug(f"Skipping {file_path}: {e}")

    def _build_reverse_map(self, search_path: str) -> dict:
        """Scan all Python files under search_path and build a reverse dependency map.

        Returns: {(dep_file, dep_name): [(caller_file, caller_name), ...]}
        """
        reverse_map = {}

        for file_path in _scan_python_files(search_path):
            self._load_file(file_path)
            if file_path not in self.file_cache:
                continue

            cache = self.file_cache[file_path]
            symbols = cache["symbols"]
            import_map = cache["import_map"]
            collector = cache["collector"]

            for sym_name, symbol in symbols.items():
                if symbol["type"] != "function":
                    continue
                try:
                    all_inline = collector.inline(symbol["node"])
                    direct_inline = collector.direct(symbol["node"])
                    dynamic_imports = collector.dynamic(symbol["node"])
                    effective_import_map = {**all_inline, **import_map, **direct_inline, **dynamic_imports}
                    deps, _ = DependencyExtractor(
                        symbols, effective_import_map, sym_name, dynamic_imports=dynamic_imports
                    ).extract(symbol["node"])

                    for dep_file, dep_name in deps:
                        key = (dep_file, dep_name)
                        if key not in reverse_map:
                            reverse_map[key] = []
                        reverse_map[key].append((file_path, sym_name))
                except Exception as e:
                    logger.debug(f"Skipping {sym_name} in {file_path}: {e}")

        return reverse_map

    def trace(self, file_path: str, name: str, graph: Graph, visited: set, reverse_map: dict):
        if (file_path, name) in visited:
            return
        visited.add((file_path, name))

        self._load_file(file_path)
        if file_path not in self.file_cache:
            return

        symbols = self.file_cache[file_path]["symbols"]
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

        for caller_file, caller_name in reverse_map.get((file_path, name), []):
            self._load_file(caller_file)
            if caller_file not in self.file_cache:
                continue

            caller_symbols = self.file_cache[caller_file]["symbols"]
            if caller_name not in caller_symbols:
                continue

            caller_symbol = caller_symbols[caller_name]
            caller_id = f"{caller_file}::{caller_name}"
            graph.create_node(caller_id, {
                "code": caller_symbol["code"],
                "type": caller_symbol["type"],
                "file_path": caller_file,
                "name": caller_name,
            })
            graph.add_edge(caller_id, node_id)
            self.trace(caller_file, caller_name, graph, visited, reverse_map)

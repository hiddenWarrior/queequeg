import ast
import os
import logging
from .graph import Graph

logger = logging.getLogger(__name__)


class Parser:
    def _get_source(self, source: str, node) -> str:
        lines = source.splitlines(keepends=True)
        if hasattr(node, 'decorator_list') and node.decorator_list:
            start = node.decorator_list[0].lineno - 1
        else:
            start = node.lineno - 1
        return ''.join(lines[start:node.end_lineno]).rstrip('\n')

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
                    "code": self._get_source(source, node),
                    "type": "function",
                    "file_path": file_path,
                    "class_prefix": prefix,
                }
            elif isinstance(node, ast.ClassDef):
                name = f"{prefix}{node.name}"
                symbols[name] = {
                    "node": node,
                    "code": self._get_source(source, node),
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
                            "code": self._get_source(source, node),
                            "type": "variable",
                            "file_path": file_path,
                            "class_prefix": "",
                        }
            elif isinstance(node, ast.AnnAssign) and not prefix:
                if isinstance(node.target, ast.Name):
                    symbols[node.target.id] = {
                        "node": node,
                        "code": self._get_source(source, node),
                        "type": "variable",
                        "file_path": file_path,
                        "class_prefix": "",
                    }

    def _index_symbols(self, source: str, tree, file_path: str) -> dict:
        symbols = {}
        self._index_body(source, tree.body, file_path, symbols)
        return symbols

    def _module_path_from_node(self, file_path: str, node) -> str:
        """Compute the absolute file path for an ast.ImportFrom node, with __init__.py fallback."""
        base_dir = os.path.dirname(os.path.abspath(file_path))
        module = node.module or ""
        level = node.level
        if level > 0:
            target_dir = base_dir
            for _ in range(level - 1):
                target_dir = os.path.dirname(target_dir)
            path = os.path.join(target_dir, module.replace(".", os.sep) + ".py")
        else:
            path = os.path.join(os.getcwd(), module.replace(".", os.sep) + ".py")
        if not os.path.isfile(path):
            init_path = os.path.join(path[:-3], "__init__.py")
            if os.path.isfile(init_path):
                return init_path
        return path

    def _extract_string_list(self, node) -> list | None:
        """Extract a flat list of strings from a list literal or concatenation of literals."""
        if isinstance(node, (ast.List, ast.Tuple)):
            result = []
            for elt in node.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    result.append(elt.value)
                else:
                    return None
            return result
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._extract_string_list(node.left)
            right = self._extract_string_list(node.right)
            if left is not None and right is not None:
                return left + right
        return None

    def _get_all_list(self, tree) -> list | None:
        """Return __all__ contents if defined, handling literals, concatenation, and += augmentation."""
        all_names = None
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        names = self._extract_string_list(node.value)
                        if names is not None:
                            all_names = names
            elif isinstance(node, ast.AugAssign):
                if isinstance(node.target, ast.Name) and node.target.id == "__all__":
                    if all_names is not None:
                        names = self._extract_string_list(node.value)
                        if names is not None:
                            all_names.extend(names)
        return all_names

    def _expand_star_import(self, module_path: str, lineno: int, visited: set = None) -> dict:
        """Recursively expand `from module import *` into individual name mappings."""
        if visited is None:
            visited = set()
        if module_path in visited:
            return {}
        visited.add(module_path)

        try:
            source, tree = self._load(module_path)
        except (FileNotFoundError, SyntaxError):
            return {}

        result = {}

        # Recursively expand any star imports this module re-exports
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        sub_path = self._module_path_from_node(module_path, node)
                        if self._is_project_file(sub_path):
                            result.update(self._expand_star_import(sub_path, lineno, visited))

        # Collect this module's own symbols and imports
        all_names = self._get_all_list(tree)
        symbols = self._index_symbols(source, tree, module_path)
        module_import_map = self._build_import_map(tree, module_path, star_visited=visited)

        if all_names is not None:
            for name in all_names:
                if name in symbols:
                    result[name] = (module_path, name, lineno)
                elif name in module_import_map:
                    imp_path, imp_name, _ = module_import_map[name]
                    if imp_name:
                        result[name] = (imp_path, imp_name, lineno)
        else:
            for name in symbols:
                if not name.startswith("_") and "." not in name:
                    result[name] = (module_path, name, lineno)

        return result

    def _resolve_import(self, file_path: str, node, star_visited: set = None) -> dict:
        result = {}

        if isinstance(node, ast.ImportFrom):
            module_path = self._module_path_from_node(file_path, node)
            if self._is_project_file(module_path):
                for alias in node.names:
                    if alias.name == "*":
                        result.update(self._expand_star_import(module_path, node.lineno, visited=star_visited))
                    else:
                        original = alias.name
                        local = alias.asname or alias.name
                        result[local] = (module_path, original, node.lineno)

        elif isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                local_name = alias.asname
                if local_name is None:
                    # dotted imports without alias (e.g. import a.b.c) bind only the
                    # top-level name which requires chained attribute resolution — skip
                    if "." in module_name:
                        continue
                    local_name = module_name
                module_path = os.path.join(os.getcwd(), module_name.replace(".", os.sep) + ".py")
                if not os.path.isfile(module_path):
                    init_path = os.path.join(module_path[:-3], "__init__.py")
                    if os.path.isfile(init_path):
                        module_path = init_path
                if self._is_project_file(module_path):
                    result[local_name] = (module_path, None, node.lineno)  # None = whole module

        return result

    def _is_project_file(self, file_path: str) -> bool:
        if not os.path.isfile(file_path):
            return False
        abs_path = os.path.abspath(file_path)
        venv_markers = [".venv", "venv", "site-packages"]
        return not any(marker in abs_path for marker in venv_markers)

    def _build_import_map(self, tree, file_path: str, star_visited: set = None) -> dict:
        """Collect only top-level imports. Inline imports are scoped to their function."""
        import_map = {}
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_map.update(self._resolve_import(file_path, node, star_visited=star_visited))
        return import_map

    def _collect_inline_imports(self, func_node, file_path: str) -> dict:
        """Collect imports declared inside a specific function body."""
        inline = {}
        for child in ast.walk(func_node):
            if child is func_node:
                continue
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                inline.update(self._resolve_import(file_path, child))
        return inline

    def _walk_current_scope(self, node):
        """Yield child nodes without recursing into nested function/class bodies."""
        for child in ast.iter_child_nodes(node):
            yield child
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                yield from self._walk_current_scope(child)

    def _get_local_names(self, node) -> set:
        """Collect all names locally assigned in a function, excluding globals/nonlocals."""
        declared_global = set()
        for child in self._walk_current_scope(node):
            if isinstance(child, ast.Global):
                declared_global.update(child.names)
            elif isinstance(child, ast.Nonlocal):
                declared_global.update(child.names)

        local_names = set()

        if hasattr(node, 'args'):
            for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                local_names.add(arg.arg)
            if node.args.vararg:
                local_names.add(node.args.vararg.arg)
            if node.args.kwarg:
                local_names.add(node.args.kwarg.arg)

        for child in self._walk_current_scope(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        local_names.add(target.id)
                    elif isinstance(target, ast.Tuple):
                        for elt in target.elts:
                            if isinstance(elt, ast.Name):
                                local_names.add(elt.id)
            elif isinstance(child, ast.AnnAssign):
                if isinstance(child.target, ast.Name):
                    local_names.add(child.target.id)
            elif isinstance(child, ast.AugAssign):
                if isinstance(child.target, ast.Name):
                    local_names.add(child.target.id)
            elif isinstance(child, (ast.For, ast.AsyncFor)):
                if isinstance(child.target, ast.Name):
                    local_names.add(child.target.id)
                elif isinstance(child.target, ast.Tuple):
                    for elt in child.target.elts:
                        if isinstance(elt, ast.Name):
                            local_names.add(elt.id)
            elif isinstance(child, ast.ExceptHandler):
                if child.name:
                    local_names.add(child.name)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local_names.add(child.name)
            elif isinstance(child, ast.ClassDef):
                local_names.add(child.name)
            elif isinstance(child, (ast.With, ast.AsyncWith)):
                for item in child.items:
                    if item.optional_vars:
                        if isinstance(item.optional_vars, ast.Name):
                            local_names.add(item.optional_vars.id)
                        elif isinstance(item.optional_vars, ast.Tuple):
                            for elt in item.optional_vars.elts:
                                if isinstance(elt, ast.Name):
                                    local_names.add(elt.id)

        return local_names - declared_global

    def extract_dependencies(self, node, symbols: dict, import_map: dict, current_name: str) -> list:
        parts = current_name.rsplit(".", 1)
        class_prefix = parts[0] + "." if len(parts) > 1 else ""

        names = set()
        module_attrs: dict[str, set] = {}  # {module_local_name: {called_attrs}}

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    names.add(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    if isinstance(child.func.value, ast.Name):
                        obj_name = child.func.value.id
                        if obj_name == "self":
                            names.add(f"{class_prefix}{child.func.attr}")
                        else:
                            names.add(obj_name)
                            module_attrs.setdefault(obj_name, set()).add(child.func.attr)
            elif isinstance(child, ast.Name):
                names.add(child.id)

        names.discard(current_name)
        names -= self._get_local_names(node)

        deps = []
        for name in names:
            in_symbols = name in symbols
            in_imports = name in import_map
            if in_symbols and in_imports:
                sym_lineno = symbols[name]["node"].lineno
                imp_lineno = import_map[name][2]
                if sym_lineno >= imp_lineno:
                    deps.append((symbols[name]["file_path"], name))
                else:
                    imp_path, imp_name, _ = import_map[name]
                    if imp_name is None:
                        for attr in module_attrs.get(name, []):
                            deps.append((imp_path, attr))
                    else:
                        deps.append((imp_path, imp_name))
            elif in_symbols:
                deps.append((symbols[name]["file_path"], name))
            elif in_imports:
                imp_path, imp_name, _ = import_map[name]
                if imp_name is None:
                    for attr in module_attrs.get(name, []):
                        deps.append((imp_path, attr))
                else:
                    deps.append((imp_path, imp_name))
        return deps

    def trace(self, file_path: str, name: str) -> Graph:
        file_path = os.path.abspath(file_path)
        source, tree = self._load(file_path)
        symbols = self._index_symbols(source, tree, file_path)

        if name not in symbols:
            raise ValueError(f"'{name}' not found in '{file_path}'")

        graph = Graph()
        file_cache = {}
        self._trace_recursive(file_path, name, graph, visited=set(), file_cache=file_cache)
        self._reconstruct_class_codes(graph, file_cache)
        return graph

    def _trace_recursive(self, file_path: str, name: str, graph: Graph, visited: set, file_cache: dict, trace_deps: bool = True):
        if (file_path, name) in visited:
            return
        visited.add((file_path, name))

        if file_path not in file_cache:
            source, tree = self._load(file_path)
            file_cache[file_path] = {
                "source": source,
                "tree": tree,
                "symbols": self._index_symbols(source, tree, file_path),
                "import_map": self._build_import_map(tree, file_path),
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

        inline_imports = self._collect_inline_imports(symbol["node"], file_path)
        effective_import_map = {**import_map, **inline_imports}
        deps = self.extract_dependencies(symbol["node"], symbols, effective_import_map, name)

        # Propagate external deps up the ancestor chain for correct topological ordering
        self._propagate_deps_to_ancestors(name, file_path, deps, symbols, graph)

        for dep_file, dep_name in deps:
            dep_id = f"{dep_file}::{dep_name}"
            graph.add_edge(node_id, dep_id)
            self._trace_recursive(dep_file, dep_name, graph, visited, file_cache)

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

    def _reconstruct_class_codes(self, graph: Graph, file_cache: dict):
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
                    parts.append(self._get_source(source, node))
            elif isinstance(node, ast.ClassDef):
                nested_name = f"{class_name}.{node.name}"
                nested_id = f"{file_path}::{nested_name}"
                if graph.has_node(nested_id):
                    parts.append(graph.get_node(nested_id)["code"])
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                parts.append(self._get_source(source, node))

        return header + "\n" + "\n\n".join(parts)

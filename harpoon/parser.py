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
            # `from . import X` — each alias is a submodule, not a name from a package
            if node.level > 0 and not node.module:
                base_dir = os.path.dirname(os.path.abspath(file_path))
                target_dir = base_dir
                for _ in range(node.level - 1):
                    target_dir = os.path.dirname(target_dir)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    submod_path = os.path.join(target_dir, alias.name.replace(".", os.sep) + ".py")
                    if not os.path.isfile(submod_path):
                        init_path = os.path.join(submod_path[:-3], "__init__.py")
                        if os.path.isfile(init_path):
                            submod_path = init_path
                    if self._is_project_file(submod_path):
                        local = alias.asname or alias.name
                        result[local] = (submod_path, None, node.lineno)
                return result

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
                # For dotted imports without alias (e.g. import a.b.c), use the full
                # dotted name as the key so chained call sites (a.b.c.func()) can resolve it.
                local_name = alias.asname if alias.asname else module_name
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

    def _iter_module_imports(self, nodes):
        """Yield import nodes from a statement list, descending into if/try but not functions/classes."""
        for node in nodes:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                yield node
            elif isinstance(node, ast.If):
                yield from self._iter_module_imports(node.body)
                yield from self._iter_module_imports(node.orelse)
            elif isinstance(node, ast.Try):
                yield from self._iter_module_imports(node.body)
                for handler in node.handlers:
                    yield from self._iter_module_imports(handler.body)
                yield from self._iter_module_imports(node.orelse)
                yield from self._iter_module_imports(node.finalbody)

    def _build_import_map(self, tree, file_path: str, star_visited: set = None) -> dict:
        """Collect top-level imports including those inside if/try blocks. Inline imports are scoped to their function."""
        import_map = {}
        for node in self._iter_module_imports(tree.body):
            import_map.update(self._resolve_import(file_path, node, star_visited=star_visited))
        return import_map

    def _collect_inline_imports(self, func_node, file_path: str) -> dict:
        """Collect all imports inside a function body, including inside nested functions."""
        inline = {}
        for child in ast.walk(func_node):
            if child is func_node:
                continue
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                inline.update(self._resolve_import(file_path, child))
        return inline

    def _collect_direct_imports(self, func_node, file_path: str) -> dict:
        """Collect imports declared directly in this function scope (not in nested functions)."""
        direct = {}
        for child in self._walk_current_scope(func_node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                direct.update(self._resolve_import(file_path, child))
        return direct

    def _collect_nested_scope_imports(self, func_node, file_path: str) -> list:
        """Return (dep_file, dep_name) pairs from all imports inside the function body."""
        result = []
        for child in ast.walk(func_node):
            if child is func_node:
                continue
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                for local_name, entry in self._resolve_import(file_path, child).items():
                    dep_file, dep_name, _ = entry
                    if dep_name:
                        result.append((dep_file, dep_name))
        return result

    def _collect_dynamic_imports(self, func_node, file_path: str) -> dict:
        """Detect importlib.import_module("literal") and import_module("literal") assignments."""
        result = {}
        for child in ast.walk(func_node):
            if not isinstance(child, ast.Assign):
                continue
            if len(child.targets) != 1 or not isinstance(child.targets[0], ast.Name):
                continue
            call = child.value
            if not isinstance(call, ast.Call) or not call.args:
                continue
            if not (isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)):
                continue
            is_importlib = (
                (isinstance(call.func, ast.Attribute)
                 and call.func.attr == 'import_module'
                 and isinstance(call.func.value, ast.Name)
                 and call.func.value.id == 'importlib')
                or
                (isinstance(call.func, ast.Name) and call.func.id == 'import_module')
            )
            if not is_importlib:
                continue
            local_name = child.targets[0].id
            module_str = call.args[0].value
            module_path = os.path.join(os.getcwd(), module_str.replace(".", os.sep) + ".py")
            if not os.path.isfile(module_path):
                init_path = os.path.join(module_path[:-3], "__init__.py")
                if os.path.isfile(init_path):
                    module_path = init_path
            if self._is_project_file(module_path):
                result[local_name] = (module_path, None, child.lineno)
        return result

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
                            elif isinstance(elt, ast.Starred) and isinstance(elt.value, ast.Name):
                                local_names.add(elt.value.id)
            elif isinstance(child, ast.AnnAssign):
                if isinstance(child.target, ast.Name):
                    local_names.add(child.target.id)
            elif isinstance(child, ast.AugAssign):
                if isinstance(child.target, ast.Name):
                    local_names.add(child.target.id)
            elif isinstance(child, ast.NamedExpr):
                local_names.add(child.target.id)
            elif isinstance(child, (ast.For, ast.AsyncFor)):
                if isinstance(child.target, ast.Name):
                    local_names.add(child.target.id)
                elif isinstance(child.target, ast.Tuple):
                    for elt in child.target.elts:
                        if isinstance(elt, ast.Name):
                            local_names.add(elt.id)
                        elif isinstance(elt, ast.Starred) and isinstance(elt.value, ast.Name):
                            local_names.add(elt.value.id)
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
            elif isinstance(child, ast.MatchAs):
                if child.name:
                    local_names.add(child.name)
            elif isinstance(child, ast.MatchStar):
                if child.name:
                    local_names.add(child.name)
            elif isinstance(child, ast.MatchMapping):
                if child.rest:
                    local_names.add(child.rest)

        return local_names - declared_global

    def extract_dependencies(self, node, symbols: dict, import_map: dict, current_name: str, dynamic_imports: dict = None, file_path: str = None) -> list:
        parts = current_name.rsplit(".", 1)
        class_prefix = parts[0] + "." if len(parts) > 1 else ""

        names = set()
        called_names = set()  # names that appear as a direct call target (for __init__ detection)
        module_attrs: dict[str, set] = {}  # {module_local_name: {called_attrs}}

        def _dotted_name_from_attr(node) -> str | None:
            """Recursively extract a dotted name string from a nested Attribute/Name chain."""
            if isinstance(node, ast.Name):
                return node.id
            if isinstance(node, ast.Attribute):
                prefix = _dotted_name_from_attr(node.value)
                if prefix is not None:
                    return f"{prefix}.{node.attr}"
            return None

        def _comp_target_names(tgt) -> set:
            if isinstance(tgt, ast.Name):
                return {tgt.id}
            if isinstance(tgt, (ast.Tuple, ast.List)):
                result = set()
                for elt in tgt.elts:
                    result |= _comp_target_names(elt)
                return result
            return set()

        def collect(n, shadowed: set):
            for child in ast.iter_child_nodes(n):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fn_params = {a.arg for a in child.args.args + child.args.posonlyargs + child.args.kwonlyargs}
                    if child.args.vararg:
                        fn_params.add(child.args.vararg.arg)
                    if child.args.kwarg:
                        fn_params.add(child.args.kwarg.arg)
                    collect(child, shadowed | fn_params)
                elif isinstance(child, ast.Lambda):
                    lam_params = {a.arg for a in child.args.args + child.args.posonlyargs + child.args.kwonlyargs}
                    if child.args.vararg:
                        lam_params.add(child.args.vararg.arg)
                    if child.args.kwarg:
                        lam_params.add(child.args.kwarg.arg)
                    collect(child, shadowed | lam_params)
                elif isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                    comp_vars = set()
                    for gen in child.generators:
                        comp_vars |= _comp_target_names(gen.target)
                    collect(child, shadowed | comp_vars)
                elif isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name):
                        func_name = child.func.id
                        if func_name not in shadowed:
                            if (func_name == 'getattr'
                                    and len(child.args) >= 2
                                    and isinstance(child.args[1], ast.Constant)
                                    and isinstance(child.args[1].value, str)):
                                obj_node = child.args[0]
                                attr_name = child.args[1].value
                                if isinstance(obj_node, ast.Name) and obj_node.id not in shadowed:
                                    if obj_node.id in ('self', 'cls') and class_prefix:
                                        names.add(f"{class_prefix}{attr_name}")
                                    else:
                                        names.add(obj_node.id)
                                        module_attrs.setdefault(obj_node.id, set()).add(attr_name)
                            else:
                                names.add(func_name)
                                called_names.add(func_name)
                    elif isinstance(child.func, ast.Attribute):
                        if isinstance(child.func.value, ast.Name):
                            obj_name = child.func.value.id
                            if obj_name not in shadowed:
                                if obj_name in ("self", "cls") and class_prefix:
                                    names.add(f"{class_prefix}{child.func.attr}")
                                else:
                                    names.add(obj_name)
                                    module_attrs.setdefault(obj_name, set()).add(child.func.attr)
                        elif isinstance(child.func.value, ast.Attribute):
                            dotted = _dotted_name_from_attr(child.func.value)
                            if dotted is not None:
                                root = dotted.split(".")[0]
                                if root not in shadowed:
                                    names.add(dotted)
                                    module_attrs.setdefault(dotted, set()).add(child.func.attr)
                        elif (isinstance(child.func.value, ast.Call)
                              and isinstance(child.func.value.func, ast.Name)
                              and child.func.value.func.id == 'super'
                              and class_prefix):
                            method_name = child.func.attr
                            class_name = class_prefix.rstrip('.')
                            if class_name in symbols:
                                for base in symbols[class_name]['node'].bases:
                                    if isinstance(base, ast.Name):
                                        names.add(f"{base.id}.{method_name}")
                    collect(child, shadowed)
                elif isinstance(child, ast.Attribute):
                    if isinstance(child.value, ast.Name):
                        obj_name = child.value.id
                        if obj_name not in shadowed:
                            if obj_name in ("self", "cls") and class_prefix:
                                names.add(f"{class_prefix}{child.attr}")
                            else:
                                names.add(obj_name)
                                module_attrs.setdefault(obj_name, set()).add(child.attr)
                    else:
                        collect(child, shadowed)
                elif isinstance(child, ast.Name):
                    if child.id not in shadowed:
                        names.add(child.id)
                else:
                    collect(child, shadowed)

        collect(node, set())

        names.discard(current_name)
        local_names = self._get_local_names(node)
        if dynamic_imports:
            local_names -= set(dynamic_imports)
        names -= local_names

        deps = []
        constructor_import_set = set()  # (imp_path, imp_name) for import calls that may be constructors
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
                if name in called_names and symbols[name]["type"] == "class":
                    init_name = f"{name}.__init__"
                    if init_name in symbols:
                        deps.append((symbols[name]["file_path"], init_name))
            elif in_imports:
                imp_path, imp_name, _ = import_map[name]
                if imp_name is None:
                    for attr in module_attrs.get(name, []):
                        deps.append((imp_path, attr))
                else:
                    deps.append((imp_path, imp_name))
                    if name in called_names:
                        constructor_import_set.add((imp_path, imp_name))
        if file_path:
            deps += self._collect_nested_scope_imports(node, file_path)
        return deps, constructor_import_set

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

        all_inline = self._collect_inline_imports(symbol["node"], file_path)
        direct_inline = self._collect_direct_imports(symbol["node"], file_path)
        dynamic_imports = self._collect_dynamic_imports(symbol["node"], file_path)
        effective_import_map = {**all_inline, **import_map, **direct_inline, **dynamic_imports}
        deps, constructor_import_set = self.extract_dependencies(symbol["node"], symbols, effective_import_map, name, dynamic_imports=dynamic_imports, file_path=file_path)

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

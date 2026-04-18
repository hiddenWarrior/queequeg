import ast
import os
import logging

logger = logging.getLogger(__name__)


class ImportResolver:
    """Resolves a single import AST node to project (file_path, name) mappings."""

    def __init__(self, file_path: str, source: str, tree):
        self._file_path = file_path
        self._source = source
        self._tree = tree
        self._star_visited: set = set()

    def resolve(self, node, star_visited: set = None) -> dict:
        """Return {local_name: (dep_file, dep_name, lineno)} for project-file imports only."""
        if star_visited is not None:
            self._star_visited = star_visited

        result = {}

        if isinstance(node, ast.ImportFrom):
            if node.level > 0 and not node.module:
                base_dir = os.path.dirname(os.path.abspath(self._file_path))
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

            module_path = self._module_path_from_node(node)
            if self._is_project_file(module_path):
                for alias in node.names:
                    if alias.name == "*":
                        result.update(self._expand_star_import(module_path, node.lineno))
                    else:
                        local = alias.asname or alias.name
                        result[local] = (module_path, alias.name, node.lineno)

        elif isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                local_name = alias.asname if alias.asname else module_name
                module_path = os.path.join(os.getcwd(), module_name.replace(".", os.sep) + ".py")
                if not os.path.isfile(module_path):
                    init_path = os.path.join(module_path[:-3], "__init__.py")
                    if os.path.isfile(init_path):
                        module_path = init_path
                if self._is_project_file(module_path):
                    result[local_name] = (module_path, None, node.lineno)

        return result

    def _module_path_from_node(self, node) -> str:
        base_dir = os.path.dirname(os.path.abspath(self._file_path))
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

    def _is_project_file(self, file_path: str) -> bool:
        if not os.path.isfile(file_path):
            return False
        abs_path = os.path.abspath(file_path)
        venv_markers = [".venv", "venv", "site-packages"]
        return not any(marker in abs_path for marker in venv_markers)

    def _expand_star_import(self, module_path: str, lineno: int) -> dict:
        if module_path in self._star_visited:
            return {}
        self._star_visited.add(module_path)

        try:
            with open(module_path) as f:
                source = f.read()
            tree = ast.parse(source)
        except (FileNotFoundError, SyntaxError):
            return {}

        result = {}

        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        sub_resolver = ImportResolver(module_path, source, tree)
                        sub_resolver._star_visited = self._star_visited
                        sub_path = sub_resolver._module_path_from_node(node)
                        if self._is_project_file(sub_path):
                            result.update(sub_resolver._expand_star_import(sub_path, lineno))

        all_names = self._get_all_list(tree)
        symbols = self._index_symbols(source, tree, module_path)
        sub_resolver = ImportResolver(module_path, source, tree)
        sub_resolver._star_visited = self._star_visited
        module_import_map = sub_resolver._build_import_map(tree)

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

    def _build_import_map(self, tree) -> dict:
        import_map = {}
        for node in self._iter_module_imports(tree.body):
            import_map.update(self.resolve(node, star_visited=self._star_visited))
        return import_map

    def _iter_module_imports(self, nodes):
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

    def _index_symbols(self, source: str, tree, file_path: str) -> dict:
        symbols = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols[node.name] = {"file_path": file_path}
            elif isinstance(node, ast.ClassDef):
                symbols[node.name] = {"file_path": file_path}
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols[target.id] = {"file_path": file_path}
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    symbols[node.target.id] = {"file_path": file_path}
        return symbols

    def _get_all_list(self, tree) -> list | None:
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

    def _extract_string_list(self, node) -> list | None:
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

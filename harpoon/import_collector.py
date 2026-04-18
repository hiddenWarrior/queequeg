import ast
import os
from .import_resolver import ImportResolver
from .ast_utils import walk_current_scope


class ImportCollector:
    """Collects imports from a function node using a resolver."""

    def __init__(self, resolver: ImportResolver):
        self._resolver = resolver

    def inline(self, func_node) -> dict:
        """All imports in function body including nested scopes, keyed by local name."""
        result = {}
        for child in ast.walk(func_node):
            if child is func_node:
                continue
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                result.update(self._resolver.resolve(child))
        return result

    def direct(self, func_node) -> dict:
        """Imports directly in function scope only, keyed by local name."""
        result = {}
        for child in walk_current_scope(func_node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                result.update(self._resolver.resolve(child))
        return result

    def nested_deps(self, func_node) -> list:
        """(dep_file, dep_name) pairs from all imports, bypassing name collision."""
        result = []
        for child in ast.walk(func_node):
            if child is func_node:
                continue
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                for local_name, entry in self._resolver.resolve(child).items():
                    dep_file, dep_name, _ = entry
                    if dep_name:
                        result.append((dep_file, dep_name))
        return result

    def dynamic(self, func_node) -> dict:
        """importlib.import_module() assignments, keyed by local name."""
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
            if self._resolver._is_project_file(module_path):
                result[local_name] = (module_path, None, child.lineno)
        return result

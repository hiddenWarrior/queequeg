import ast
from .ast_utils import dotted_name_from_attr, comp_target_names, get_local_names


class DependencyExtractor:
    """Extracts (dep_file, dep_name) pairs from a single function/class AST node."""

    def __init__(self, symbols: dict, import_map: dict, current_name: str, dynamic_imports: dict = None):
        parts = current_name.rsplit(".", 1)
        self._class_prefix = parts[0] + "." if len(parts) > 1 else ""
        self._current_name = current_name
        self._symbols = symbols
        self._import_map = import_map
        self._dynamic_imports = dynamic_imports or {}

        self._names: set = set()
        self._called_names: set = set()
        self._module_attrs: dict[str, set] = {}

    def extract(self, node) -> tuple:
        self._collect(node, set())
        self._names.discard(self._current_name)
        local_names = get_local_names(node)
        if self._dynamic_imports:
            local_names -= set(self._dynamic_imports)
        self._names -= local_names
        return self._resolve()

    def _collect(self, node, shadowed: set):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_params = {a.arg for a in child.args.args + child.args.posonlyargs + child.args.kwonlyargs}
                if child.args.vararg:
                    fn_params.add(child.args.vararg.arg)
                if child.args.kwarg:
                    fn_params.add(child.args.kwarg.arg)
                self._collect(child, shadowed | fn_params)
            elif isinstance(child, ast.Lambda):
                lam_params = {a.arg for a in child.args.args + child.args.posonlyargs + child.args.kwonlyargs}
                if child.args.vararg:
                    lam_params.add(child.args.vararg.arg)
                if child.args.kwarg:
                    lam_params.add(child.args.kwarg.arg)
                self._collect(child, shadowed | lam_params)
            elif isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                comp_vars = set()
                for gen in child.generators:
                    comp_vars |= comp_target_names(gen.target)
                self._collect(child, shadowed | comp_vars)
            elif isinstance(child, ast.Call):
                self._handle_call(child, shadowed)
            elif isinstance(child, ast.Attribute):
                if isinstance(child.value, ast.Name):
                    obj_name = child.value.id
                    if obj_name not in shadowed:
                        if obj_name in ("self", "cls") and self._class_prefix:
                            self._names.add(f"{self._class_prefix}{child.attr}")
                        else:
                            self._names.add(obj_name)
                            self._module_attrs.setdefault(obj_name, set()).add(child.attr)
                else:
                    self._collect(child, shadowed)
            elif isinstance(child, ast.Name):
                if child.id not in shadowed:
                    self._names.add(child.id)
            else:
                self._collect(child, shadowed)

    def _handle_call(self, child, shadowed: set):
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
                        if obj_node.id in ('self', 'cls') and self._class_prefix:
                            self._names.add(f"{self._class_prefix}{attr_name}")
                        else:
                            self._names.add(obj_node.id)
                            self._module_attrs.setdefault(obj_node.id, set()).add(attr_name)
                else:
                    self._names.add(func_name)
                    self._called_names.add(func_name)
        elif isinstance(child.func, ast.Attribute):
            if isinstance(child.func.value, ast.Name):
                obj_name = child.func.value.id
                if obj_name not in shadowed:
                    if obj_name in ("self", "cls") and self._class_prefix:
                        self._names.add(f"{self._class_prefix}{child.func.attr}")
                    else:
                        self._names.add(obj_name)
                        self._module_attrs.setdefault(obj_name, set()).add(child.func.attr)
            elif isinstance(child.func.value, ast.Attribute):
                dotted = dotted_name_from_attr(child.func.value)
                if dotted is not None:
                    root = dotted.split(".")[0]
                    if root not in shadowed:
                        self._names.add(dotted)
                        self._module_attrs.setdefault(dotted, set()).add(child.func.attr)
            elif (isinstance(child.func.value, ast.Call)
                  and isinstance(child.func.value.func, ast.Name)
                  and child.func.value.func.id == 'super'
                  and self._class_prefix):
                method_name = child.func.attr
                class_name = self._class_prefix.rstrip('.')
                if class_name in self._symbols:
                    for base in self._symbols[class_name]['node'].bases:
                        if isinstance(base, ast.Name):
                            self._names.add(f"{base.id}.{method_name}")
        self._collect(child, shadowed)

    def _resolve(self) -> tuple:
        deps = []
        constructor_import_set = set()
        for name in self._names:
            in_symbols = name in self._symbols
            in_imports = name in self._import_map
            if in_symbols and in_imports:
                sym_lineno = self._symbols[name]["node"].lineno
                imp_lineno = self._import_map[name][2]
                if sym_lineno >= imp_lineno:
                    deps.append((self._symbols[name]["file_path"], name))
                else:
                    imp_path, imp_name, _ = self._import_map[name]
                    if imp_name is None:
                        for attr in self._module_attrs.get(name, []):
                            deps.append((imp_path, attr))
                    else:
                        deps.append((imp_path, imp_name))
            elif in_symbols:
                deps.append((self._symbols[name]["file_path"], name))
                if name in self._called_names and self._symbols[name]["type"] == "class":
                    init_name = f"{name}.__init__"
                    if init_name in self._symbols:
                        deps.append((self._symbols[name]["file_path"], init_name))
            elif in_imports:
                imp_path, imp_name, _ = self._import_map[name]
                if imp_name is None:
                    for attr in self._module_attrs.get(name, []):
                        deps.append((imp_path, attr))
                else:
                    deps.append((imp_path, imp_name))
                    if name in self._called_names:
                        constructor_import_set.add((imp_path, imp_name))
        return deps, constructor_import_set

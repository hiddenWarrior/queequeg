import ast


def get_source(source: str, node) -> str:
    """Extract source text for an AST node, including decorators, stripping trailing newline."""
    lines = source.splitlines(keepends=True)
    if hasattr(node, 'decorator_list') and node.decorator_list:
        start = node.decorator_list[0].lineno - 1
    else:
        start = node.lineno - 1
    return ''.join(lines[start:node.end_lineno]).rstrip('\n')


def walk_current_scope(node):
    """Yield child nodes without recursing into nested function/class bodies."""
    for child in ast.iter_child_nodes(node):
        yield child
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield from walk_current_scope(child)


def dotted_name_from_attr(node) -> str | None:
    """Recursively extract a dotted name string from a nested Attribute/Name chain."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted_name_from_attr(node.value)
        if prefix is not None:
            return f"{prefix}.{node.attr}"
    return None


def comp_target_names(tgt) -> set:
    """Collect all bound names from a comprehension target (handles tuples/lists)."""
    if isinstance(tgt, ast.Name):
        return {tgt.id}
    if isinstance(tgt, (ast.Tuple, ast.List)):
        result = set()
        for elt in tgt.elts:
            result |= comp_target_names(elt)
        return result
    return set()


def get_local_names(node) -> set:
    """Collect all names locally assigned in a function, excluding globals/nonlocals."""
    declared_global = set()
    for child in walk_current_scope(node):
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

    for child in walk_current_scope(node):
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

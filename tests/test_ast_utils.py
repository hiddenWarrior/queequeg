import ast
import unittest
from queequeg.ast_utils import (
    walk_current_scope,
    dotted_name_from_attr,
    comp_target_names,
    get_local_names,
)


def parse_func(code: str):
    return ast.parse(code).body[0]


def parse_expr(code: str):
    return ast.parse(code, mode="eval").body


def node_types(nodes):
    return [type(n).__name__ for n in nodes]


class TestWalkCurrentScope(unittest.TestCase):
    def test_yields_direct_children(self):
        func = parse_func("""
def f():
    x = 1
    y = 2
""")
        nodes = list(walk_current_scope(func))
        self.assertTrue(any(isinstance(n, ast.Assign) for n in nodes))

    def test_recurses_into_if_block(self):
        func = parse_func("""
def f():
    if True:
        x = 1
""")
        nodes = list(walk_current_scope(func))
        assigns = [n for n in nodes if isinstance(n, ast.Assign)]
        self.assertEqual(len(assigns), 1)

    def test_recurses_into_try_block(self):
        func = parse_func("""
def f():
    try:
        x = 1
    except Exception:
        pass
""")
        nodes = list(walk_current_scope(func))
        assigns = [n for n in nodes if isinstance(n, ast.Assign)]
        self.assertEqual(len(assigns), 1)

    def test_stops_at_nested_function(self):
        func = parse_func("""
def f():
    def inner():
        x = 1
""")
        nodes = list(walk_current_scope(func))
        assigns = [n for n in nodes if isinstance(n, ast.Assign)]
        self.assertEqual(len(assigns), 0)

    def test_stops_at_nested_class(self):
        func = parse_func("""
def f():
    class Inner:
        x = 1
""")
        nodes = list(walk_current_scope(func))
        assigns = [n for n in nodes if isinstance(n, ast.Assign)]
        self.assertEqual(len(assigns), 0)

    def test_recurses_into_for_loop(self):
        func = parse_func("""
def f():
    for i in range(10):
        x = 1
""")
        nodes = list(walk_current_scope(func))
        assigns = [n for n in nodes if isinstance(n, ast.Assign)]
        self.assertEqual(len(assigns), 1)


class TestDottedNameFromAttr(unittest.TestCase):
    def test_name_node_returns_id(self):
        node = parse_expr("foo")
        self.assertEqual(dotted_name_from_attr(node), "foo")

    def test_single_attribute(self):
        node = parse_expr("a.b")
        self.assertEqual(dotted_name_from_attr(node), "a.b")

    def test_chained_attributes(self):
        node = parse_expr("a.b.c")
        self.assertEqual(dotted_name_from_attr(node), "a.b.c")

    def test_deeply_chained(self):
        node = parse_expr("a.b.c.d")
        self.assertEqual(dotted_name_from_attr(node), "a.b.c.d")

    def test_non_name_base_returns_none(self):
        node = parse_expr("f().attr")
        self.assertIsNone(dotted_name_from_attr(node))

    def test_constant_returns_none(self):
        node = parse_expr("42")
        self.assertIsNone(dotted_name_from_attr(node))


class TestCompTargetNames(unittest.TestCase):
    def test_simple_name(self):
        node = parse_expr("x")
        self.assertEqual(comp_target_names(node), {"x"})

    def test_tuple_of_names(self):
        node = parse_expr("(x, y)")
        self.assertEqual(comp_target_names(node), {"x", "y"})

    def test_list_of_names(self):
        node = parse_expr("[x, y]")
        self.assertEqual(comp_target_names(node), {"x", "y"})

    def test_nested_tuple(self):
        node = parse_expr("(x, (y, z))")
        self.assertEqual(comp_target_names(node), {"x", "y", "z"})

    def test_non_name_returns_empty(self):
        node = parse_expr("42")
        self.assertEqual(comp_target_names(node), set())


class TestGetLocalNames(unittest.TestCase):
    def test_function_parameters(self):
        func = parse_func("def f(a, b): pass")
        self.assertIn("a", get_local_names(func))
        self.assertIn("b", get_local_names(func))

    def test_vararg(self):
        func = parse_func("def f(*args): pass")
        self.assertIn("args", get_local_names(func))

    def test_kwarg(self):
        func = parse_func("def f(**kwargs): pass")
        self.assertIn("kwargs", get_local_names(func))

    def test_assignment(self):
        func = parse_func("""
def f():
    x = 1
""")
        self.assertIn("x", get_local_names(func))

    def test_augmented_assignment(self):
        func = parse_func("""
def f():
    x += 1
""")
        self.assertIn("x", get_local_names(func))

    def test_annotated_assignment(self):
        func = parse_func("""
def f():
    x: int = 1
""")
        self.assertIn("x", get_local_names(func))

    def test_for_loop_target(self):
        func = parse_func("""
def f():
    for i in range(10):
        pass
""")
        self.assertIn("i", get_local_names(func))

    def test_tuple_unpack_in_for(self):
        func = parse_func("""
def f():
    for a, b in items:
        pass
""")
        names = get_local_names(func)
        self.assertIn("a", names)
        self.assertIn("b", names)

    def test_with_statement_var(self):
        func = parse_func("""
def f():
    with open("f") as fp:
        pass
""")
        self.assertIn("fp", get_local_names(func))

    def test_exception_handler_name(self):
        func = parse_func("""
def f():
    try:
        pass
    except Exception as e:
        pass
""")
        self.assertIn("e", get_local_names(func))

    def test_nested_function_name_included(self):
        func = parse_func("""
def f():
    def inner():
        pass
""")
        self.assertIn("inner", get_local_names(func))

    def test_nested_function_params_excluded(self):
        func = parse_func("""
def f():
    def inner(x):
        pass
""")
        self.assertNotIn("x", get_local_names(func))

    def test_global_excluded(self):
        func = parse_func("""
def f():
    global x
    x = 1
""")
        self.assertNotIn("x", get_local_names(func))

    def test_nonlocal_excluded(self):
        func = parse_func("""
def f():
    def inner():
        nonlocal x
        x = 1
""")
        inner = parse_func("""
def inner():
    nonlocal x
    x = 1
""")
        self.assertNotIn("x", get_local_names(inner))

    def test_walrus_operator(self):
        func = parse_func("""
def f():
    if (n := 10) > 5:
        pass
""")
        self.assertIn("n", get_local_names(func))

    def test_tuple_unpack_assignment(self):
        func = parse_func("""
def f():
    a, b = 1, 2
""")
        names = get_local_names(func)
        self.assertIn("a", names)
        self.assertIn("b", names)

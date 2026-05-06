import ast
import os
import unittest
from queequeg.dependency_extractor import DependencyExtractor

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def parse_func(code: str):
    return ast.parse(code).body[0]


def parse_class(code: str):
    return ast.parse(code).body[0]


def make_extractor(code: str, symbols: dict = None, import_map: dict = None, current_name: str = "f", dynamic_imports: dict = None):
    node = parse_func(code)
    return DependencyExtractor(
        symbols=symbols or {},
        import_map=import_map or {},
        current_name=current_name,
        dynamic_imports=dynamic_imports,
    ), node


class TestBasicNameResolution(unittest.TestCase):
    def test_no_deps_for_standalone(self):
        ext, node = make_extractor("def f(): return 1")
        deps, _ = ext.extract(node)
        self.assertEqual(deps, [])

    def test_resolves_local_symbol(self):
        helper_node = parse_func("def helper(): pass")
        symbols = {"helper": {"node": helper_node, "file_path": "/a.py", "type": "function"}}
        ext, node = make_extractor("def f(): helper()", symbols=symbols)
        deps, _ = ext.extract(node)
        self.assertIn(("/a.py", "helper"), deps)

    def test_resolves_imported_name(self):
        import_map = {"helper": ("/b.py", "helper", 1)}
        ext, node = make_extractor("def f(): helper()", import_map=import_map)
        deps, _ = ext.extract(node)
        self.assertIn(("/b.py", "helper"), deps)

    def test_local_var_shadows_symbol(self):
        helper_node = parse_func("def helper(): pass")
        symbols = {"helper": {"node": helper_node, "file_path": "/a.py", "type": "function"}}
        ext, node = make_extractor("def f():\n    helper = 1\n    return helper", symbols=symbols)
        deps, _ = ext.extract(node)
        self.assertNotIn(("/a.py", "helper"), deps)

    def test_param_shadows_symbol(self):
        helper_node = parse_func("def helper(): pass")
        symbols = {"helper": {"node": helper_node, "file_path": "/a.py", "type": "function"}}
        ext, node = make_extractor("def f(helper): return helper()", symbols=symbols)
        deps, _ = ext.extract(node)
        self.assertNotIn(("/a.py", "helper"), deps)

    def test_for_loop_var_shadows_symbol(self):
        helper_node = parse_func("def helper(): pass")
        symbols = {"helper": {"node": helper_node, "file_path": "/a.py", "type": "function"}}
        ext, node = make_extractor("def f():\n    for helper in []:\n        pass", symbols=symbols)
        deps, _ = ext.extract(node)
        self.assertNotIn(("/a.py", "helper"), deps)

    def test_self_referential_dep_excluded(self):
        self_node = parse_func("def f(): f()")
        symbols = {"f": {"node": self_node, "file_path": "/a.py", "type": "function"}}
        ext, node = make_extractor("def f(): f()", symbols=symbols)
        deps, _ = ext.extract(node)
        self.assertNotIn(("/a.py", "f"), deps)


class TestModuleAttrResolution(unittest.TestCase):
    def test_resolves_module_attribute(self):
        import_map = {"mod": ("/mod.py", None, 1)}
        ext, node = make_extractor("def f(): mod.helper()", import_map=import_map)
        deps, _ = ext.extract(node)
        self.assertIn(("/mod.py", "helper"), deps)

    def test_does_not_add_module_itself_as_dep(self):
        import_map = {"mod": ("/mod.py", None, 1)}
        ext, node = make_extractor("def f(): mod.helper()", import_map=import_map)
        deps, _ = ext.extract(node)
        self.assertNotIn(("/mod.py", None), deps)

    def test_resolves_multiple_attrs_from_module(self):
        import_map = {"mod": ("/mod.py", None, 1)}
        ext, node = make_extractor("def f(): mod.a(); mod.b()", import_map=import_map)
        deps, _ = ext.extract(node)
        self.assertIn(("/mod.py", "a"), deps)
        self.assertIn(("/mod.py", "b"), deps)


class TestSelfAndClsDeps(unittest.TestCase):
    def test_self_attr_resolves_to_class_method(self):
        init_node = parse_func("def __init__(self): pass")
        helper_node = parse_func("def _helper(self): pass")
        symbols = {
            "MyClass.__init__": {"node": init_node, "file_path": "/a.py", "type": "function"},
            "MyClass._helper": {"node": helper_node, "file_path": "/a.py", "type": "function"},
        }
        ext, node = make_extractor(
            "def __init__(self): self._helper()",
            symbols=symbols,
            current_name="MyClass.__init__",
        )
        deps, _ = ext.extract(node)
        self.assertIn(("/a.py", "MyClass._helper"), deps)

    def test_cls_attr_resolves_to_class_method(self):
        create_node = parse_func("def create(cls): pass")
        helper_node = parse_func("def _setup(cls): pass")
        symbols = {
            "MyClass.create": {"node": create_node, "file_path": "/a.py", "type": "function"},
            "MyClass._setup": {"node": helper_node, "file_path": "/a.py", "type": "function"},
        }
        ext, node = make_extractor(
            "def create(cls): cls._setup()",
            symbols=symbols,
            current_name="MyClass.create",
        )
        deps, _ = ext.extract(node)
        self.assertIn(("/a.py", "MyClass._setup"), deps)


class TestConstructorDeps(unittest.TestCase):
    def test_called_class_triggers_constructor(self):
        cls_node = parse_class("class Foo: pass")
        init_node = parse_func("def __init__(self): pass")
        symbols = {
            "Foo": {"node": cls_node, "file_path": "/a.py", "type": "class"},
            "Foo.__init__": {"node": init_node, "file_path": "/a.py", "type": "function"},
        }
        ext, node = make_extractor("def f(): Foo()", symbols=symbols)
        deps, _ = ext.extract(node)
        self.assertIn(("/a.py", "Foo"), deps)
        self.assertIn(("/a.py", "Foo.__init__"), deps)

    def test_called_imported_class_in_constructor_import_set(self):
        import_map = {"Foo": ("/b.py", "Foo", 1)}
        ext, node = make_extractor("def f(): Foo()", import_map=import_map)
        deps, constructor_import_set = ext.extract(node)
        self.assertIn(("/b.py", "Foo"), deps)
        self.assertIn(("/b.py", "Foo"), constructor_import_set)

    def test_non_called_class_not_in_constructor_import_set(self):
        import_map = {"Foo": ("/b.py", "Foo", 1)}
        ext, node = make_extractor("def f(): x = Foo", import_map=import_map)
        _, constructor_import_set = ext.extract(node)
        self.assertNotIn(("/b.py", "Foo"), constructor_import_set)


class TestLambdaShadowing(unittest.TestCase):
    def test_lambda_param_shadows_outer(self):
        helper_node = parse_func("def helper(): pass")
        symbols = {"helper": {"node": helper_node, "file_path": "/a.py", "type": "function"}}
        ext, node = make_extractor("def f(): g = lambda helper: helper()", symbols=symbols)
        deps, _ = ext.extract(node)
        self.assertNotIn(("/a.py", "helper"), deps)

    def test_lambda_free_var_resolves(self):
        helper_node = parse_func("def helper(): pass")
        symbols = {"helper": {"node": helper_node, "file_path": "/a.py", "type": "function"}}
        ext, node = make_extractor("def f(): g = lambda x: helper(x)", symbols=symbols)
        deps, _ = ext.extract(node)
        self.assertIn(("/a.py", "helper"), deps)


class TestComprehensionShadowing(unittest.TestCase):
    def test_comp_var_shadows_outer(self):
        helper_node = parse_func("def helper(): pass")
        symbols = {"helper": {"node": helper_node, "file_path": "/a.py", "type": "function"}}
        ext, node = make_extractor("def f(): return [helper for helper in []]", symbols=symbols)
        deps, _ = ext.extract(node)
        self.assertNotIn(("/a.py", "helper"), deps)

    def test_comp_free_var_resolves(self):
        helper_node = parse_func("def helper(): pass")
        symbols = {"helper": {"node": helper_node, "file_path": "/a.py", "type": "function"}}
        ext, node = make_extractor("def f(): return [helper(x) for x in []]", symbols=symbols)
        deps, _ = ext.extract(node)
        self.assertIn(("/a.py", "helper"), deps)


class TestGetattrHandling(unittest.TestCase):
    def test_getattr_with_string_literal_resolves_attr(self):
        import_map = {"mod": ("/mod.py", None, 1)}
        ext, node = make_extractor("def f(): getattr(mod, 'helper')", import_map=import_map)
        deps, _ = ext.extract(node)
        self.assertIn(("/mod.py", "helper"), deps)

    def test_getattr_self_resolves_to_class_method(self):
        method_node = parse_func("def _helper(self): pass")
        symbols = {
            "MyClass.run": {"node": parse_func("def run(self): pass"), "file_path": "/a.py", "type": "function"},
            "MyClass._helper": {"node": method_node, "file_path": "/a.py", "type": "function"},
        }
        ext, node = make_extractor(
            "def run(self): getattr(self, '_helper')()",
            symbols=symbols,
            current_name="MyClass.run",
        )
        deps, _ = ext.extract(node)
        self.assertIn(("/a.py", "MyClass._helper"), deps)


class TestSymbolVsImportPrecedence(unittest.TestCase):
    def test_symbol_wins_when_defined_after_import(self):
        helper_node = ast.parse("def helper(): pass").body[0]
        helper_node.lineno = 10
        symbols = {"helper": {"node": helper_node, "file_path": "/a.py", "type": "function"}}
        import_map = {"helper": ("/b.py", "helper", 5)}  # lineno 5 < symbol lineno 10
        ext, node = make_extractor("def f(): helper()", symbols=symbols, import_map=import_map)
        deps, _ = ext.extract(node)
        self.assertIn(("/a.py", "helper"), deps)
        self.assertNotIn(("/b.py", "helper"), deps)

    def test_import_wins_when_defined_before_symbol(self):
        helper_node = ast.parse("def helper(): pass").body[0]
        helper_node.lineno = 3
        symbols = {"helper": {"node": helper_node, "file_path": "/a.py", "type": "function"}}
        import_map = {"helper": ("/b.py", "helper", 10)}  # lineno 10 > symbol lineno 3
        ext, node = make_extractor("def f(): helper()", symbols=symbols, import_map=import_map)
        deps, _ = ext.extract(node)
        self.assertIn(("/b.py", "helper"), deps)
        self.assertNotIn(("/a.py", "helper"), deps)

import os
import unittest
from harpoon.parser import Parser

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    return os.path.join(FIXTURES, name)


def node_names(graph):
    return {n.split("::")[-1] for n in graph.nodes()}


class TestSimple(unittest.TestCase):
    def test_standalone_has_no_dependencies(self):
        graph = Parser().trace(fixture("simple.py"), "standalone")
        self.assertEqual(node_names(graph), {"standalone"})

    def test_function_depends_on_called_function(self):
        graph = Parser().trace(fixture("simple.py"), "uses_helper")
        self.assertIn("helper", node_names(graph))

    def test_function_depends_on_global_variable(self):
        graph = Parser().trace(fixture("simple.py"), "uses_global")
        self.assertIn("MAX_SIZE", node_names(graph))

    def test_function_depends_on_global_and_helper(self):
        graph = Parser().trace(fixture("simple.py"), "uses_global_and_helper")
        names = node_names(graph)
        self.assertIn("MAX_SIZE", names)
        self.assertIn("helper", names)

    def test_local_variable_shadowing_global_not_a_dependency(self):
        graph = Parser().trace(fixture("simple.py"), "shadows_global")
        self.assertNotIn("MAX_SIZE", node_names(graph))

    def test_global_declaration_still_a_dependency(self):
        graph = Parser().trace(fixture("simple.py"), "uses_global_explicitly")
        self.assertIn("MAX_SIZE", node_names(graph))

    def test_for_loop_variable_shadowing_function_not_a_dependency(self):
        graph = Parser().trace(fixture("simple.py"), "shadows_with_for_loop")
        self.assertNotIn("helper", node_names(graph))

    def test_argument_shadowing_function_not_a_dependency(self):
        graph = Parser().trace(fixture("simple.py"), "shadows_with_arg")
        self.assertNotIn("helper", node_names(graph))

    def test_varargs_shadowing_not_a_dependency(self):
        graph = Parser().trace(fixture("simple.py"), "shadows_with_varargs")
        self.assertNotIn("helper", node_names(graph))
        self.assertNotIn("MAX_SIZE", node_names(graph))

    def test_tuple_unpack_shadowing_not_a_dependency(self):
        # helper is bound via tuple unpack — should not be traced as module-level helper
        # This test currently FAILS — tuple unpack targets not added to local_names yet
        graph = Parser().trace(fixture("simple.py"), "shadows_with_tuple_unpack")
        self.assertNotIn("helper", node_names(graph))

    def test_context_manager_variable_shadowing_not_a_dependency(self):
        # `with ... as helper` binds helper locally — should not be traced as module-level helper
        # This test currently FAILS — with-statement targets not added to local_names yet
        graph = Parser().trace(fixture("simple.py"), "shadows_with_context_manager")
        self.assertNotIn("helper", node_names(graph))

    def test_except_variable_shadowing_not_a_dependency(self):
        graph = Parser().trace(fixture("simple.py"), "shadows_with_except")
        self.assertNotIn("helper", node_names(graph))

    def test_inner_function_shadowing_not_a_dependency(self):
        graph = Parser().trace(fixture("simple.py"), "shadows_with_inner_function")
        self.assertNotIn("helper", node_names(graph))

    def test_default_arg_calling_function_is_a_dependency(self):
        graph = Parser().trace(fixture("simple.py"), "uses_helper_in_default_arg")
        self.assertIn("helper", node_names(graph))

    def test_nonlocal_variable_not_traced_as_module_dependency(self):
        # outer_with_nonlocal assigns `helper` locally; inner uses `nonlocal helper`
        # the outer function's `helper` is local — should NOT trace module-level helper
        # This test currently FAILS — nonlocal in nested function incorrectly bleeds into outer scope analysis
        graph = Parser().trace(fixture("simple.py"), "outer_with_nonlocal")
        self.assertNotIn("helper", node_names(graph))

    def test_for_loop_tuple_unpack_not_a_dependency(self):
        graph = Parser().trace(fixture("simple.py"), "shadows_with_for_tuple")
        self.assertNotIn("helper", node_names(graph))

    def test_multiple_context_managers_not_dependencies(self):
        graph = Parser().trace(fixture("simple.py"), "shadows_with_multiple_context_managers")
        self.assertNotIn("helper", node_names(graph))
        self.assertNotIn("MAX_SIZE", node_names(graph))

    def test_variable_with_dependency_traced(self):
        graph = Parser().trace(fixture("simple.py"), "DEPENDENT_VAR")
        self.assertIn("MAX_SIZE", node_names(graph))


class TestCrossFile(unittest.TestCase):
    def test_imported_function_traced(self):
        graph = Parser().trace(fixture("cross_file_a.py"), "uses_imported_function")
        self.assertIn("shared_helper", node_names(graph))

    def test_imported_class_traced(self):
        graph = Parser().trace(fixture("cross_file_a.py"), "uses_imported_class")
        self.assertIn("SharedClass", node_names(graph))


class TestDecorators(unittest.TestCase):
    def test_single_decorator_included(self):
        graph = Parser().trace(fixture("decorators.py"), "single_decorated")
        self.assertIn("my_decorator", node_names(graph))

    def test_multi_decorator_included(self):
        graph = Parser().trace(fixture("decorators.py"), "multi_decorated")
        names = node_names(graph)
        self.assertIn("my_decorator", names)
        self.assertIn("another_decorator", names)

    def test_multiline_decorator_included(self):
        graph = Parser().trace(fixture("decorators.py"), "multiline_decorated")
        self.assertIn("another_decorator", node_names(graph))

    def test_class_decorator_included(self):
        graph = Parser().trace(fixture("decorators.py"), "DecoratedClass")
        self.assertIn("my_decorator", node_names(graph))


class TestShadowImport(unittest.TestCase):
    def test_local_definition_shadows_import(self):
        graph = Parser().trace(fixture("shadow_import.py"), "uses_shadowed")
        # shared_helper is defined locally AND imported — local should win
        result = graph.nodes()
        shared_node = next(n for n in result if n.endswith("::shared_helper"))
        self.assertIn("shadow_import.py", shared_node)

    def test_imported_version_not_in_graph(self):
        graph = Parser().trace(fixture("shadow_import.py"), "uses_shadowed")
        result = graph.nodes()
        shared_nodes = [n for n in result if n.endswith("::shared_helper")]
        # only one shared_helper — the local one
        self.assertEqual(len(shared_nodes), 1)
        self.assertIn("shadow_import.py", shared_nodes[0])

    def test_import_after_local_definition_wins(self):
        graph = Parser().trace(fixture("shadow_import.py"), "uses_import_after_local")
        result = graph.nodes()
        # import comes after local def — imported shared_helper from cross_file_b should be in graph
        cross_file_nodes = [n for n in result if "cross_file_b" in n and n.endswith("::shared_helper")]
        self.assertEqual(len(cross_file_nodes), 1)
        # local definition should NOT be in graph
        local_nodes = [n for n in result if "shadow_import" in n and n.endswith("::local_first")]
        self.assertEqual(len(local_nodes), 0)


class TestCircular(unittest.TestCase):
    def test_circular_dependency_does_not_crash(self):
        graph = Parser().trace(fixture("circular.py"), "entry")
        names = node_names(graph)
        self.assertIn("ping", names)
        self.assertIn("pong", names)


class TestInlineImport(unittest.TestCase):
    def test_inline_import_traced_as_dependency(self):
        graph = Parser().trace(fixture("inline_import.py"), "uses_inline_import")
        self.assertIn("shared_helper", node_names(graph))

    def test_import_inside_nested_function(self):
        graph = Parser().trace(fixture("nested_import.py"), "outer")
        self.assertIn("shared_helper", node_names(graph))

    def test_import_inside_nested_function_in_method(self):
        graph = Parser().trace(fixture("nested_import.py"), "MyClass.method")
        self.assertIn("shared_helper", node_names(graph))

    def test_inline_import_trumps_local_in_owning_function(self):
        # uses_inline_import has an inline `from ... import helper` — should use that, not the local def
        graph = Parser().trace(fixture("inline_import_scope.py"), "uses_inline_import")
        nodes = graph.nodes()
        cross_file_nodes = [n for n in nodes if "cross_file_b" in n and n.endswith("::helper")]
        self.assertEqual(len(cross_file_nodes), 1)

    def test_inline_import_in_sibling_does_not_affect_other_function(self):
        # uses_local_helper only uses the module-level helper(), not the inline import in its sibling
        # This test currently FAILS — it documents a known scope-bleed bug
        graph = Parser().trace(fixture("inline_import_scope.py"), "uses_local_helper")
        nodes = graph.nodes()
        local_nodes = [n for n in nodes if "inline_import_scope" in n and n.endswith("::helper")]
        self.assertEqual(len(local_nodes), 1, "local helper should be the dependency, not the cross-file one")

    def test_toplevel_import_after_local_definition_wins(self):
        # local_helper_v2 is defined locally first, then a top-level import rebinds it — import should win
        graph = Parser().trace(fixture("inline_import_scope.py"), "uses_import_after_local_def")
        nodes = graph.nodes()
        cross_file_nodes = [n for n in nodes if "cross_file_b" in n and n.endswith("::helper")]
        self.assertEqual(len(cross_file_nodes), 1)
        local_nodes = [n for n in nodes if "inline_import_scope" in n and n.endswith("::local_helper_v2")]
        self.assertEqual(len(local_nodes), 0)


class TestClasses(unittest.TestCase):
    def test_method_in_class(self):
        graph = Parser().trace(fixture("classes.py"), "Animal.speak")
        self.assertIn("Animal.speak", node_names(graph))

    def test_method_depends_on_top_level_function(self):
        graph = Parser().trace(fixture("classes.py"), "Animal.speak")
        self.assertIn("helper", node_names(graph))

    def test_method_depends_on_another_method(self):
        graph = Parser().trace(fixture("classes.py"), "Dog.fetch")
        self.assertIn("Dog.speak", node_names(graph))

    def test_nested_class_method(self):
        graph = Parser().trace(fixture("classes.py"), "Outer.Inner.method")
        self.assertIn("helper", node_names(graph))

    def test_outer_method_depends_on_inner_class(self):
        graph = Parser().trace(fixture("classes.py"), "Outer.outer_method")
        self.assertIn("Outer.Inner", node_names(graph))

    def test_method_includes_class_itself(self):
        graph = Parser().trace(fixture("classes.py"), "Animal.speak")
        self.assertIn("Animal", node_names(graph))

    def test_method_includes_class_variable(self):
        graph = Parser().trace(fixture("classes.py"), "Dog.fetch")
        self.assertIn("Dog", node_names(graph))

    def test_method_does_not_include_unrelated_sibling(self):
        graph = Parser().trace(fixture("classes.py"), "Dog.fetch")
        self.assertNotIn("Dog.sit", node_names(graph))

    def test_nested_class_includes_class_variable(self):
        graph = Parser().trace(fixture("classes.py"), "Outer.Inner.method")
        self.assertIn("Outer.Inner", node_names(graph))

    def test_base_class_is_a_dependency(self):
        graph = Parser().trace(fixture("classes.py"), "Dog")
        self.assertIn("Animal", node_names(graph))


class TestAsync(unittest.TestCase):
    def test_async_function_traced(self):
        graph = Parser().trace(fixture("async_func.py"), "async_uses_helper")
        self.assertIn("async_helper", node_names(graph))

    def test_async_function_itself_in_graph(self):
        graph = Parser().trace(fixture("async_func.py"), "async_uses_helper")
        self.assertIn("async_uses_helper", node_names(graph))


class TestCodeGeneration(unittest.TestCase):
    def test_method_code_in_output(self):
        graph = Parser().trace(fixture("classes.py"), "Animal.speak")
        from harpoon.serializers.code import CodeSerializer
        result = CodeSerializer().translate(graph)
        self.assertIn("def speak", result)

    def test_class_appears_in_output(self):
        graph = Parser().trace(fixture("classes.py"), "Animal.speak")
        from harpoon.serializers.code import CodeSerializer
        result = CodeSerializer().translate(graph)
        self.assertIn("class Animal", result)

    def test_unrelated_sibling_not_in_output(self):
        graph = Parser().trace(fixture("classes.py"), "Dog.fetch")
        from harpoon.serializers.code import CodeSerializer
        result = CodeSerializer().translate(graph)
        self.assertNotIn("def sit", result)


class TestErrorHandling(unittest.TestCase):
    def test_function_not_found_raises(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            Parser().trace(fixture("simple.py"), "nonexistent")


class TestDiamondDependency(unittest.TestCase):
    def test_shared_node_appears_once(self):
        graph = Parser().trace(fixture("diamond.py"), "top")
        names = node_names(graph)
        self.assertIn("shared", names)
        self.assertIn("left", names)
        self.assertIn("right", names)
        # shared should appear exactly once as a node
        all_node_ids = graph.nodes()
        shared_nodes = [n for n in all_node_ids if n.endswith("::shared")]
        self.assertEqual(len(shared_nodes), 1)

    def test_all_nodes_reachable(self):
        graph = Parser().trace(fixture("diamond.py"), "top")
        names = node_names(graph)
        self.assertEqual(names, {"top", "left", "right", "shared"})


class TestDeepChain(unittest.TestCase):
    def test_full_chain_traced(self):
        graph = Parser().trace(fixture("deep_chain.py"), "a")
        names = node_names(graph)
        self.assertIn("b", names)
        self.assertIn("c", names)
        self.assertIn("d", names)

    def test_chain_order_in_output(self):
        from harpoon.serializers.code import CodeSerializer
        graph = Parser().trace(fixture("deep_chain.py"), "a")
        result = CodeSerializer().translate(graph)
        self.assertLess(result.index("def d"), result.index("def c"))
        self.assertLess(result.index("def c"), result.index("def b"))
        self.assertLess(result.index("def b"), result.index("def a"))


class TestStarImportAllEdgeCases(unittest.TestCase):
    def test_reexported_via_all_is_traced(self):
        # __init__.py imports core_func from submodule and re-exports it via __all__
        # currently FAILS — _expand_star_import only checks symbols, not import_map
        graph = Parser().trace(fixture("reexport_user.py"), "uses_reexported")
        self.assertIn("core_func", node_names(graph))

    def test_reexported_node_points_to_original_file(self):
        # core_func should trace back to core.py, not __init__.py
        graph = Parser().trace(fixture("reexport_user.py"), "uses_reexported")
        nodes = graph.nodes()
        core_nodes = [n for n in nodes if n.endswith("::core_func")]
        self.assertEqual(len(core_nodes), 1)
        self.assertIn("core.py", core_nodes[0])

    def test_concatenated_all_exports_traced(self):
        # __all__ = ['func_one'] + ['func_two'] — concatenation should be resolved
        # currently FAILS — _get_all_list only handles plain list literals
        graph = Parser().trace(fixture("dynamic_all_user.py"), "uses_concatenated_all")
        self.assertIn("func_two", node_names(graph))

    def test_augmented_all_exports_traced(self):
        # __all__ += ['func_three'] — augmented assignment should be picked up
        # currently FAILS — _get_all_list does not handle AugAssign
        graph = Parser().trace(fixture("dynamic_all_user.py"), "uses_augmented_all")
        self.assertIn("func_three", node_names(graph))

    def test_hidden_func_not_in_dynamic_all(self):
        # func_hidden is not in __all__ so it should not be traced
        graph = Parser().trace(fixture("dynamic_all_user.py"), "uses_hidden")
        self.assertNotIn("func_hidden", node_names(graph))


class TestStarImport(unittest.TestCase):
    def test_all_exported_function_traced(self):
        graph = Parser().trace(fixture("star_all_import.py"), "uses_exported")
        self.assertIn("exported_func", node_names(graph))

    def test_all_hidden_function_not_traced(self):
        # hidden_func is not in __all__ so star import should not include it
        graph = Parser().trace(fixture("star_all_import.py"), "uses_hidden")
        self.assertNotIn("hidden_func", node_names(graph))

    def test_star_import_dependency_traced(self):
        # shared_helper comes from `from cross_file_b import *` — should be traced
        # This test currently FAILS — star imports are not resolved yet
        graph = Parser().trace(fixture("star_import.py"), "uses_star_import")
        self.assertIn("shared_helper", node_names(graph))

    def test_chained_star_import_dependency_traced(self):
        # deep_helper lives in star_file_c, re-exported by star_file_b via *, then star-imported here
        # This test currently FAILS — chained star imports are not resolved yet
        graph = Parser().trace(fixture("star_import.py"), "uses_chained_star_import")
        self.assertIn("deep_helper", node_names(graph))


class TestPackageImport(unittest.TestCase):
    def test_package_init_function_traced(self):
        # `from mypackage import package_func` where mypackage is a directory
        # currently FAILS — resolver builds mypackage.py instead of mypackage/__init__.py
        graph = Parser().trace(fixture("package_import.py"), "uses_package")
        self.assertIn("package_func", node_names(graph))

    def test_package_init_node_has_correct_file(self):
        # the traced node should point to mypackage/__init__.py not mypackage.py
        graph = Parser().trace(fixture("package_import.py"), "uses_package")
        nodes = graph.nodes()
        package_nodes = [n for n in nodes if "mypackage" in n and n.endswith("::package_func")]
        self.assertEqual(len(package_nodes), 1)
        self.assertIn("__init__.py", package_nodes[0])


class TestPlainImport(unittest.TestCase):
    def test_plain_import_with_alias_traced(self):
        # `import module as m; m.func()` — should trace func from module
        # currently FAILS — plain imports not resolved
        graph = Parser().trace(fixture("plain_import.py"), "uses_plain_import")
        self.assertIn("shared_helper", node_names(graph))

    def test_plain_import_dependency_has_correct_file(self):
        graph = Parser().trace(fixture("plain_import.py"), "uses_plain_import")
        nodes = graph.nodes()
        dep_nodes = [n for n in nodes if "cross_file_b" in n and n.endswith("::shared_helper")]
        self.assertEqual(len(dep_nodes), 1)


class TestCircularStarImport(unittest.TestCase):
    def test_circular_star_import_does_not_recurse(self):
        # circular_a imports * from circular_b, which imports * from circular_a
        graph = Parser().trace(fixture("circular_user.py"), "uses_circular")
        self.assertIn("func_a", node_names(graph))

    def test_circular_star_import_does_not_include_other_side(self):
        # func_b lives in circular_b — it's reachable via *, but uses_circular doesn't call it
        graph = Parser().trace(fixture("circular_user.py"), "uses_circular")
        self.assertNotIn("func_b", node_names(graph))


class TestGetAttrLiteral(unittest.TestCase):
    def test_getattr_self_literal_method_traced(self):
        # getattr(self, "handle_a")() should resolve to Dispatcher.handle_a
        graph = Parser().trace(fixture("getattr_literal.py"), "Dispatcher.dispatch_literal")
        self.assertIn("Dispatcher.handle_a", node_names(graph))

    def test_getattr_self_dynamic_does_not_error(self):
        # getattr(self, variable)() — dynamic, should not crash, just not trace
        graph = Parser().trace(fixture("getattr_literal.py"), "Dispatcher.dispatch_dynamic")
        self.assertIn("Dispatcher.dispatch_dynamic", node_names(graph))

    def test_getattr_imported_module_literal_traced(self):
        # getattr(cfb, "shared_helper")() — should trace shared_helper from cross_file_b
        graph = Parser().trace(fixture("getattr_literal.py"), "calls_via_getattr")
        self.assertIn("shared_helper", node_names(graph))


class TestReflection(unittest.TestCase):
    def test_getattr_access_no_call_traced(self):
        # getattr(self, "method_a") without calling — still a dependency
        graph = Parser().trace(fixture("reflection.py"), "ReflectionClass.access_via_getattr")
        self.assertIn("ReflectionClass.method_a", node_names(graph))

    def test_getattr_three_arg_form_traced(self):
        # getattr(self, "method_a", None) — 3-arg form should still trace
        graph = Parser().trace(fixture("reflection.py"), "ReflectionClass.getattr_with_default")
        self.assertIn("ReflectionClass.method_a", node_names(graph))

    def test_getattr_dynamic_does_not_error(self):
        # getattr(self, variable) — unresolvable, should not crash
        graph = Parser().trace(fixture("reflection.py"), "ReflectionClass.getattr_dynamic")
        self.assertIn("ReflectionClass.getattr_dynamic", node_names(graph))

    def test_getattr_imported_attr_access_traced(self):
        # getattr(cfb, "shared_helper") without calling — still a dependency
        graph = Parser().trace(fixture("reflection.py"), "access_imported_attr")
        self.assertIn("shared_helper", node_names(graph))


class TestImportlibImport(unittest.TestCase):
    def test_importlib_import_module_literal_traced(self):
        # importlib.import_module("literal") assigned to mod, then mod.func() — should trace
        graph = Parser().trace(fixture("importlib_import.py"), "uses_importlib")
        self.assertIn("shared_helper", node_names(graph))

    def test_importlib_import_module_correct_file(self):
        graph = Parser().trace(fixture("importlib_import.py"), "uses_importlib")
        nodes = graph.nodes()
        dep_nodes = [n for n in nodes if "cross_file_b" in n and n.endswith("::shared_helper")]
        self.assertEqual(len(dep_nodes), 1)

    def test_importlib_from_import_traced(self):
        # from importlib import import_module; mod = import_module("literal") — should also trace
        graph = Parser().trace(fixture("importlib_import.py"), "uses_importlib_from_import")
        self.assertIn("shared_helper", node_names(graph))


class TestCrossFileDecorator(unittest.TestCase):
    def test_imported_decorator_traced(self):
        # @my_decorator imported from another file should be a dependency
        graph = Parser().trace(fixture("decorator_cross.py"), "uses_imported_decorator")
        self.assertIn("my_decorator", node_names(graph))

    def test_imported_factory_decorator_traced(self):
        # @another_decorator("arg") imported from another file should be a dependency
        graph = Parser().trace(fixture("decorator_cross.py"), "uses_factory_decorator")
        self.assertIn("another_decorator", node_names(graph))


class TestConstructorDep(unittest.TestCase):
    def test_constructor_call_traces_init(self):
        # MyService() should trace MyService.__init__
        graph = Parser().trace(fixture("constructor_dep.py"), "creates_service")
        self.assertIn("MyService.__init__", node_names(graph))

    def test_constructor_init_traces_its_deps(self):
        # MyService.__init__ calls init_helper — should be transitively traced
        graph = Parser().trace(fixture("constructor_dep.py"), "creates_service")
        self.assertIn("init_helper", node_names(graph))


class TestSuperCall(unittest.TestCase):
    def test_super_call_traces_parent_method(self):
        # super().compute() in Child.compute should trace Base.compute
        graph = Parser().trace(fixture("super_call.py"), "Child.compute")
        self.assertIn("Base.compute", node_names(graph))

    def test_super_call_transitively_traces_parent_deps(self):
        # Base.compute calls base_helper — should appear transitively
        graph = Parser().trace(fixture("super_call.py"), "Child.compute")
        self.assertIn("base_helper", node_names(graph))


class TestConditionalImport(unittest.TestCase):
    def test_if_branch_import_traced(self):
        # import inside `if` at module level should be resolved
        graph = Parser().trace(fixture("conditional_import.py"), "uses_if_import")
        self.assertIn("shared_helper", node_names(graph))

    def test_try_branch_import_traced(self):
        # import inside `try` at module level should be resolved
        graph = Parser().trace(fixture("conditional_import.py"), "uses_try_import")
        self.assertIn("SharedClass", node_names(graph))


class TestWalrusOperator(unittest.TestCase):
    def test_walrus_target_not_traced_as_dep(self):
        # shared_helper := get_data() — walrus shadows the import, should NOT be a dep
        graph = Parser().trace(fixture("walrus_shadow.py"), "uses_walrus")
        self.assertNotIn("shared_helper", node_names(graph))

    def test_walrus_function_call_inside_still_traced(self):
        # get_data() is called — should be traced regardless of walrus
        graph = Parser().trace(fixture("walrus_shadow.py"), "uses_walrus")
        self.assertIn("get_data", node_names(graph))


class TestMatchStatement(unittest.TestCase):
    def test_match_case_binding_not_traced_as_dep(self):
        # case str() as shared_helper — binds shared_helper locally, should NOT be a dep
        graph = Parser().trace(fixture("match_shadow.py"), "uses_match")
        self.assertNotIn("shared_helper", node_names(graph))


class TestCrossFileConstructorInit(unittest.TestCase):
    def test_imported_class_constructor_traces_init(self):
        # MyService() imported from another file — should trace MyService.__init__
        graph = Parser().trace(fixture("cross_file_init_user.py"), "creates_imported_service")
        self.assertIn("MyService.__init__", node_names(graph))

    def test_imported_class_constructor_traces_init_deps(self):
        # MyService.__init__ calls init_helper — should appear transitively
        graph = Parser().trace(fixture("cross_file_init_user.py"), "creates_imported_service")
        self.assertIn("init_helper", node_names(graph))


class TestDynamicImportScope(unittest.TestCase):
    def test_importlib_in_nested_function_not_outer_dep(self):
        # importlib.import_module() inside inner() should NOT affect outer()'s deps
        graph = Parser().trace(fixture("importlib_nested.py"), "outer")
        self.assertNotIn("shared_helper", node_names(graph))


class TestStarUnpack(unittest.TestCase):
    def test_starred_unpack_target_not_traced_as_dep(self):
        # first, *helper = [...] — *helper shadows the import, should NOT be a dep
        graph = Parser().trace(fixture("star_unpack_shadow.py"), "uses_star_unpack")
        self.assertNotIn("helper", node_names(graph))


class TestLambdaScope(unittest.TestCase):
    def test_lambda_param_not_traced_as_dep(self):
        # lambda shared_helper: ... — param shadows the import, should NOT be a dep
        graph = Parser().trace(fixture("lambda_shadow.py"), "uses_lambda")
        self.assertNotIn("shared_helper", node_names(graph))


class TestClassMethod(unittest.TestCase):
    def test_cls_method_call_traces_sibling(self):
        # cls.process() in create() should trace MyClass.process
        graph = Parser().trace(fixture("classmethod_dep.py"), "MyClass.create")
        self.assertIn("MyClass.process", node_names(graph))

    def test_cls_method_call_transitively_traces_deps(self):
        # MyClass.process calls standalone_helper — should appear transitively
        graph = Parser().trace(fixture("classmethod_dep.py"), "MyClass.create")
        self.assertIn("standalone_helper", node_names(graph))


class TestInlineImportNestedScope(unittest.TestCase):
    def test_nested_function_inline_import_not_outer_dep(self):
        # inner()'s inline import of 'helper as target_func' should NOT override outer's import
        graph = Parser().trace(fixture("inline_nested_scope.py"), "outer_uses_import")
        self.assertNotIn("helper", node_names(graph))

    def test_outer_import_still_traced_correctly(self):
        # outer's target_func() should resolve to shared_helper (top-level import)
        graph = Parser().trace(fixture("inline_nested_scope.py"), "outer_uses_import")
        self.assertIn("shared_helper", node_names(graph))


class TestLambdaOuterDep(unittest.TestCase):
    def test_outer_import_not_suppressed_by_lambda_param(self):
        # lambda param 'shared_helper' should not suppress the outer call to shared_helper()
        graph = Parser().trace(fixture("lambda_outer_dep.py"), "uses_lambda_and_outer_import")
        self.assertIn("shared_helper", node_names(graph))


class TestCompVarShadow(unittest.TestCase):
    def test_comprehension_var_not_traced_as_dep(self):
        # [shared_helper for shared_helper in range(10)] — comp var, NOT a dep
        graph = Parser().trace(fixture("comp_var_shadow.py"), "uses_comp_var")
        self.assertNotIn("shared_helper", node_names(graph))


class TestConstructorInitOrder(unittest.TestCase):
    def test_imported_init_ordered_before_caller_class(self):
        # Builder.build calls MyService() — MyService.__init__ should appear before Builder
        from harpoon.serializers.code import CodeSerializer
        graph = Parser().trace(fixture("class_init_order.py"), "Builder.build")
        result = CodeSerializer().translate(graph)
        self.assertIn("def __init__", result)
        self.assertLess(result.index("def __init__"), result.index("class Builder"))


class TestLambdaFreeVar(unittest.TestCase):
    def test_lambda_free_var_is_traced(self):
        # shared_helper used as free var inside lambda (not a param) — should be traced
        graph = Parser().trace(fixture("lambda_free_var.py"), "uses_lambda_with_free_var")
        self.assertIn("shared_helper", node_names(graph))

    def test_lambda_free_var_not_param_still_dep(self):
        # confirm x (the param) is not mistakenly traced as dep
        graph = Parser().trace(fixture("lambda_free_var.py"), "uses_lambda_with_free_var")
        self.assertNotIn("x", node_names(graph))


class TestLambdaMultiple(unittest.TestCase):
    def test_lambda_shadowed_param_not_traced(self):
        # first lambda uses shared_helper as param, never called outside — NOT a dep
        graph = Parser().trace(fixture("lambda_multi.py"), "uses_multiple_lambdas")
        self.assertNotIn("shared_helper", node_names(graph))

    def test_lambda_free_var_in_other_lambda_traced(self):
        # second lambda uses helper as free var — IS a dep
        graph = Parser().trace(fixture("lambda_multi.py"), "uses_multiple_lambdas")
        self.assertIn("helper", node_names(graph))


class TestCompFreeVar(unittest.TestCase):
    def test_comp_free_var_is_traced(self):
        # shared_helper(x) inside comprehension where x is the iter var — shared_helper IS a dep
        graph = Parser().trace(fixture("comp_free_var.py"), "uses_comp_with_free_var")
        self.assertIn("shared_helper", node_names(graph))

    def test_comp_iter_var_not_traced(self):
        # x is the iter var — NOT a dep
        graph = Parser().trace(fixture("comp_free_var.py"), "uses_comp_with_free_var")
        self.assertNotIn("x", node_names(graph))


class TestDictCompShadow(unittest.TestCase):
    def test_dict_comp_iter_var_not_traced(self):
        # {sh: sh*2 for sh in range(10)} — sh is only a comp iter var, NOT a dep
        graph = Parser().trace(fixture("dict_comp_shadow.py"), "uses_dict_comp_var")
        self.assertNotIn("shared_helper", node_names(graph))


class TestSetCompShadow(unittest.TestCase):
    def test_set_comp_iter_var_not_traced(self):
        # {sh for sh in range(10)} — sh is only a comp iter var, NOT a dep
        graph = Parser().trace(fixture("set_comp_shadow.py"), "uses_set_comp_var")
        self.assertNotIn("shared_helper", node_names(graph))


class TestGenExpShadow(unittest.TestCase):
    def test_genexp_iter_var_not_traced(self):
        # (sh for sh in range(10)) — sh is only a genexp iter var, NOT a dep
        graph = Parser().trace(fixture("genexp_shadow.py"), "uses_genexp_var")
        self.assertNotIn("shared_helper", node_names(graph))


class TestCompVarThenOuterCall(unittest.TestCase):
    def test_comp_var_shadow_does_not_suppress_outer_call(self):
        # shared_helper used as comp iter var AND called outside comp — outer call IS a dep
        graph = Parser().trace(fixture("comp_var_then_outer_call.py"), "comp_var_then_outer_call")
        self.assertIn("shared_helper", node_names(graph))


class TestSelfInLambda(unittest.TestCase):
    def test_self_method_call_inside_lambda_traced(self):
        # self.helper() inside lambda body — should trace LambdaClass.helper
        graph = Parser().trace(fixture("self_in_lambda.py"), "LambdaClass.method_with_self_in_lambda")
        self.assertIn("LambdaClass.helper", node_names(graph))


class TestDepInControlFlow(unittest.TestCase):
    def test_dep_in_try_body_traced(self):
        graph = Parser().trace(fixture("dep_in_try.py"), "dep_in_try_body")
        self.assertIn("shared_helper", node_names(graph))

    def test_dep_in_except_body_traced(self):
        graph = Parser().trace(fixture("dep_in_try.py"), "dep_in_except_body")
        self.assertIn("helper", node_names(graph))

    def test_dep_in_finally_body_traced(self):
        graph = Parser().trace(fixture("dep_in_try.py"), "dep_in_finally_body")
        self.assertIn("shared_helper", node_names(graph))

    def test_dep_in_for_body_traced(self):
        graph = Parser().trace(fixture("dep_in_loop.py"), "dep_in_for_body")
        self.assertIn("shared_helper", node_names(graph))

    def test_dep_in_while_body_traced(self):
        graph = Parser().trace(fixture("dep_in_loop.py"), "dep_in_while_body")
        self.assertIn("helper", node_names(graph))

    def test_dep_in_with_body_traced(self):
        graph = Parser().trace(fixture("dep_in_loop.py"), "dep_in_with_body")
        self.assertIn("shared_helper", node_names(graph))


class TestSelfInComp(unittest.TestCase):
    def test_self_method_in_comp_body_traced(self):
        # self.transform() inside list comp — should trace CompClass.transform
        graph = Parser().trace(fixture("self_in_comp.py"), "CompClass.method_with_self_in_comp")
        self.assertIn("CompClass.transform", node_names(graph))

    def test_getattr_self_in_comp_body_traced(self):
        # getattr(self, "transform") inside list comp — should trace CompClass.transform
        graph = Parser().trace(fixture("self_in_comp.py"), "CompClass.method_with_getattr_in_comp")
        self.assertIn("CompClass.transform", node_names(graph))

    def test_comp_iter_var_not_traced_even_with_self_calls(self):
        # x is the comp iter var, not a dep
        graph = Parser().trace(fixture("self_in_comp.py"), "CompClass.method_with_self_in_comp")
        self.assertNotIn("x", node_names(graph))


class TestGetAttrInLambda(unittest.TestCase):
    def test_getattr_self_in_lambda_body_traced(self):
        # getattr(self, "helper") inside lambda — should trace GetAttrLambdaClass.helper
        graph = Parser().trace(fixture("getattr_in_lambda.py"), "GetAttrLambdaClass.method_with_getattr_in_lambda")
        self.assertIn("GetAttrLambdaClass.helper", node_names(graph))


class TestMultiGenComp(unittest.TestCase):
    def test_multi_gen_iter_vars_not_traced(self):
        # [... for row in ... for x in row] — row and x are both iter vars, NOT deps
        graph = Parser().trace(fixture("multi_gen_comp.py"), "uses_multi_gen_comp")
        self.assertNotIn("row", node_names(graph))
        self.assertNotIn("x", node_names(graph))

    def test_multi_gen_free_var_traced(self):
        # shared_helper is a free var — IS a dep
        graph = Parser().trace(fixture("multi_gen_comp.py"), "uses_multi_gen_comp")
        self.assertIn("shared_helper", node_names(graph))

    def test_nested_comp_iter_vars_not_traced(self):
        # [[...] for row in ...] with inner [... for x in row] — both iter vars NOT deps
        graph = Parser().trace(fixture("multi_gen_comp.py"), "uses_nested_comp")
        self.assertNotIn("row", node_names(graph))
        self.assertNotIn("x", node_names(graph))

    def test_nested_comp_free_var_traced(self):
        graph = Parser().trace(fixture("multi_gen_comp.py"), "uses_nested_comp")
        self.assertIn("shared_helper", node_names(graph))


class TestConstructorInLoop(unittest.TestCase):
    def test_constructor_in_for_loop_traces_init(self):
        # MyService() inside a for loop — called_names must still be tracked
        graph = Parser().trace(fixture("constructor_in_loop.py"), "creates_in_loop")
        self.assertIn("MyService.__init__", node_names(graph))

    def test_constructor_in_try_block_traces_init(self):
        # MyService() inside a try block — called_names must still be tracked
        graph = Parser().trace(fixture("constructor_in_loop.py"), "creates_in_try")
        self.assertIn("MyService.__init__", node_names(graph))


class TestNestedFuncParamShadow(unittest.TestCase):
    def test_nested_func_param_not_traced_as_dep(self):
        # def inner(shared_helper): — param shadows the outer import, NOT a dep of outer
        graph = Parser().trace(fixture("nested_func_param_shadow.py"), "outer_with_nested_param")
        self.assertNotIn("shared_helper", node_names(graph))

    def test_nested_func_free_var_still_traced(self):
        # def inner(): shared_helper() — free variable, IS a dep of outer
        graph = Parser().trace(fixture("nested_func_param_shadow.py"), "outer_with_nested_free_var")
        self.assertIn("shared_helper", node_names(graph))


class TestRelativePackageImport(unittest.TestCase):
    def test_from_dot_import_module_traces_dep(self):
        # from . import utils; utils.util_func() — should trace util_func
        graph = Parser().trace(fixture("relpkg/user.py"), "uses_relative_module")
        self.assertIn("util_func", node_names(graph))


class TestChainedAttrAccess(unittest.TestCase):
    def test_plain_import_alias_single_level_traced(self):
        # import mod as m; m.func() — single-level attribute call works
        graph = Parser().trace(fixture("plain_import.py"), "uses_plain_import")
        self.assertIn("shared_helper", node_names(graph))

    def test_plain_import_no_alias_chained_not_traced(self):
        # import a.b.c; a.b.c.func() — deeply chained, currently not resolved
        # known gap: only single-level obj.attr() is tracked
        # currently FAILS
        graph = Parser().trace(fixture("plain_import.py"), "uses_plain_import_no_alias")
        self.assertIn("shared_helper", node_names(graph))


class TestExternalImports(unittest.TestCase):
    def test_stdlib_not_traced(self):
        graph = Parser().trace(fixture("external_import.py"), "uses_external")
        names = node_names(graph)
        self.assertNotIn("os", names)
        self.assertNotIn("json", names)

    def test_function_itself_is_traced(self):
        graph = Parser().trace(fixture("external_import.py"), "uses_external")
        self.assertIn("uses_external", node_names(graph))


class TestMultiInheritSuper(unittest.TestCase):
    def test_super_traces_all_base_methods(self):
        # C(A, B).compute calls super().compute() — should trace both A.compute and B.compute
        graph = Parser().trace(fixture("multi_inherit_super.py"), "C.compute")
        names = node_names(graph)
        self.assertIn("A.compute", names)
        self.assertIn("B.compute", names)

    def test_super_multi_inherit_traces_base_deps(self):
        # A.compute calls helper_a, B.compute calls helper_b — both appear transitively
        graph = Parser().trace(fixture("multi_inherit_super.py"), "C.compute")
        names = node_names(graph)
        self.assertIn("helper_a", names)
        self.assertIn("helper_b", names)


class TestTypeAnnotationDep(unittest.TestCase):
    def test_param_annotation_is_dep(self):
        # def foo(x: MyModel) — MyModel referenced in annotation, IS a dep
        graph = Parser().trace(fixture("type_annotation_dep.py"), "annotated_param")
        self.assertIn("MyModel", node_names(graph))

    def test_return_annotation_is_dep(self):
        # def foo() -> MyModel — MyModel referenced in return annotation, IS a dep
        graph = Parser().trace(fixture("type_annotation_dep.py"), "annotated_return")
        self.assertIn("MyModel", node_names(graph))


class TestAsyncShadow(unittest.TestCase):
    def test_async_for_loop_var_not_traced(self):
        # async for shared_helper in ... — loop var shadows the import, NOT a dep
        graph = Parser().trace(fixture("async_shadow.py"), "async_for_shadow")
        self.assertNotIn("shared_helper", node_names(graph))

    def test_async_with_var_not_traced(self):
        # async with ... as shared_helper — context var shadows the import, NOT a dep
        graph = Parser().trace(fixture("async_shadow.py"), "async_with_shadow")
        self.assertNotIn("shared_helper", node_names(graph))


class TestNoInitConstructor(unittest.TestCase):
    def test_constructor_no_init_does_not_add_init_dep(self):
        # NoInit() — class has no __init__, should NOT add NoInit.__init__ to graph
        graph = Parser().trace(fixture("no_init_class.py"), "creates_no_init")
        self.assertNotIn("NoInit.__init__", node_names(graph))

    def test_constructor_no_init_class_still_traced(self):
        # NoInit is still instantiated — the class node IS in graph
        graph = Parser().trace(fixture("no_init_class.py"), "creates_no_init")
        self.assertIn("NoInit", node_names(graph))


class TestRelativeSubmoduleDirectImport(unittest.TestCase):
    def test_from_dot_submodule_import_func_traces_dep(self):
        # from .utils import util_func — relative import with explicit module name
        graph = Parser().trace(fixture("relpkg/direct_user.py"), "uses_direct_relative_import")
        self.assertIn("util_func", node_names(graph))


if __name__ == "__main__":
    unittest.main()

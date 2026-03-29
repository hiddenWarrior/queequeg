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


class TestExternalImports(unittest.TestCase):
    def test_stdlib_not_traced(self):
        graph = Parser().trace(fixture("external_import.py"), "uses_external")
        names = node_names(graph)
        self.assertNotIn("os", names)
        self.assertNotIn("json", names)

    def test_function_itself_is_traced(self):
        graph = Parser().trace(fixture("external_import.py"), "uses_external")
        self.assertIn("uses_external", node_names(graph))


if __name__ == "__main__":
    unittest.main()

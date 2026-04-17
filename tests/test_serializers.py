import os
import json
import unittest
from harpoon.parser import Parser
from harpoon.serializers.code import CodeSerializer
from harpoon.serializers.json import JsonSerializer

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    return os.path.join(FIXTURES, name)


class TestCodeSerializer(unittest.TestCase):
    def test_output_contains_function_code(self):
        graph = Parser().trace(fixture("simple.py"), "uses_helper")
        result = CodeSerializer().translate(graph)
        self.assertIn("def uses_helper", result)

    def test_output_contains_dependency_code(self):
        graph = Parser().trace(fixture("simple.py"), "uses_helper")
        result = CodeSerializer().translate(graph)
        self.assertIn("def helper", result)

    def test_output_contains_file_comment(self):
        graph = Parser().trace(fixture("simple.py"), "uses_helper")
        result = CodeSerializer().translate(graph)
        self.assertIn("# file:", result)

    def test_dependency_appears_before_dependent(self):
        graph = Parser().trace(fixture("simple.py"), "uses_helper")
        result = CodeSerializer().translate(graph)
        helper_pos = result.index("def helper")
        uses_helper_pos = result.index("def uses_helper")
        self.assertLess(helper_pos, uses_helper_pos)

    def test_cross_file_dependency_included(self):
        graph = Parser().trace(fixture("cross_file_a.py"), "uses_imported_function")
        result = CodeSerializer().translate(graph)
        self.assertIn("def shared_helper", result)
        self.assertIn("def uses_imported_function", result)

    def test_global_variable_appears_in_output(self):
        graph = Parser().trace(fixture("simple.py"), "uses_global")
        result = CodeSerializer().translate(graph)
        self.assertIn("MAX_SIZE = 100", result)

    def test_decorator_appears_in_output(self):
        graph = Parser().trace(fixture("decorators.py"), "single_decorated")
        result = CodeSerializer().translate(graph)
        self.assertIn("@my_decorator", result)

    def test_cross_file_nodes_have_different_file_comments(self):
        graph = Parser().trace(fixture("cross_file_a.py"), "uses_imported_function")
        result = CodeSerializer().translate(graph)
        file_comments = [l for l in result.splitlines() if l.startswith("# file:")]
        file_paths = {c.split("# file:")[-1].strip() for c in file_comments}
        self.assertGreater(len(file_paths), 1)

    def test_same_file_symbols_under_one_file_comment(self):
        # helper and uses_helper are both in simple.py — only one # file: comment for simple.py
        graph = Parser().trace(fixture("simple.py"), "uses_helper")
        result = CodeSerializer().translate(graph)
        file_comments = [l for l in result.splitlines() if l.startswith("# file:")]
        simple_comments = [c for c in file_comments if "simple.py" in c]
        self.assertEqual(len(simple_comments), 1)

    def test_file_comment_appears_once_per_file(self):
        # deep_chain has 4 symbols all in one file — should have exactly one # file: comment
        graph = Parser().trace(fixture("deep_chain.py"), "a")
        result = CodeSerializer().translate(graph)
        file_comments = [l for l in result.splitlines() if l.startswith("# file:")]
        self.assertEqual(len(file_comments), 1)

    def test_dependency_file_comment_before_dependent_file_comment(self):
        # cross_file_b.py (dep) should have its file section before cross_file_a.py (dependent)
        graph = Parser().trace(fixture("cross_file_a.py"), "uses_imported_function")
        result = CodeSerializer().translate(graph)
        lines = result.splitlines()
        file_comments = [(i, l) for i, l in enumerate(lines) if l.startswith("# file:")]
        self.assertEqual(len(file_comments), 2)
        self.assertIn("cross_file_b", file_comments[0][1])
        self.assertIn("cross_file_a", file_comments[1][1])


class TestJsonSerializer(unittest.TestCase):
    def test_output_is_valid_json(self):
        graph = Parser().trace(fixture("simple.py"), "uses_helper")
        result = JsonSerializer().translate(graph)
        parsed = json.loads(result)
        self.assertIsInstance(parsed, dict)

    def test_output_contains_node(self):
        graph = Parser().trace(fixture("simple.py"), "uses_helper")
        result = json.loads(JsonSerializer().translate(graph))
        keys = [k.split("::")[-1] for k in result]
        self.assertIn("uses_helper", keys)

    def test_output_contains_dependency(self):
        graph = Parser().trace(fixture("simple.py"), "uses_helper")
        result = json.loads(JsonSerializer().translate(graph))
        node = next(v for k, v in result.items() if k.endswith("::uses_helper"))
        dep_names = [d.split("::")[-1] for d in node["dependencies"]]
        self.assertIn("helper", dep_names)

    def test_output_contains_file_path(self):
        graph = Parser().trace(fixture("simple.py"), "standalone")
        result = json.loads(JsonSerializer().translate(graph))
        node = next(v for k, v in result.items() if k.endswith("::standalone"))
        self.assertIn("simple.py", node["file_path"])

    def test_output_contains_type(self):
        graph = Parser().trace(fixture("simple.py"), "standalone")
        result = json.loads(JsonSerializer().translate(graph))
        node = next(v for k, v in result.items() if k.endswith("::standalone"))
        self.assertEqual(node["type"], "function")

    def test_variable_type_is_correct(self):
        graph = Parser().trace(fixture("simple.py"), "uses_global")
        result = json.loads(JsonSerializer().translate(graph))
        node = next(v for k, v in result.items() if k.endswith("::MAX_SIZE"))
        self.assertEqual(node["type"], "variable")

    def test_nested_dependencies_in_graph(self):
        graph = Parser().trace(fixture("simple.py"), "uses_global_and_helper")
        result = json.loads(JsonSerializer().translate(graph))
        keys = [k.split("::")[-1] for k in result]
        self.assertIn("uses_global_and_helper", keys)
        self.assertIn("helper", keys)
        self.assertIn("MAX_SIZE", keys)

    def test_cross_file_node_has_correct_file_path(self):
        graph = Parser().trace(fixture("cross_file_a.py"), "uses_imported_function")
        result = json.loads(JsonSerializer().translate(graph))
        node = next(v for k, v in result.items() if k.endswith("::shared_helper"))
        self.assertIn("cross_file_b.py", node["file_path"])


class TestCodeSerializerEdgeCases(unittest.TestCase):
    def test_circular_dependency_produces_output(self):
        graph = Parser().trace(fixture("circular.py"), "entry")
        result = CodeSerializer().translate(graph)
        self.assertIn("def ping", result)
        self.assertIn("def pong", result)

    def test_async_function_in_output(self):
        graph = Parser().trace(fixture("async_func.py"), "async_uses_helper")
        result = CodeSerializer().translate(graph)
        self.assertIn("async def async_helper", result)
        self.assertIn("async def async_uses_helper", result)

    def test_variable_with_dependency_in_output(self):
        graph = Parser().trace(fixture("simple.py"), "DEPENDENT_VAR")
        result = CodeSerializer().translate(graph)
        self.assertIn("MAX_SIZE = 100", result)
        self.assertIn("DEPENDENT_VAR = MAX_SIZE", result)

    def test_dependency_appears_before_dependent_in_variable_output(self):
        graph = Parser().trace(fixture("simple.py"), "DEPENDENT_VAR")
        result = CodeSerializer().translate(graph)
        self.assertLess(result.index("MAX_SIZE = 100"), result.index("DEPENDENT_VAR = MAX_SIZE"))

    def test_file_comment_appears_before_its_code(self):
        graph = Parser().trace(fixture("cross_file_a.py"), "uses_imported_function")
        result = CodeSerializer().translate(graph)
        for line_a, line_b in zip(result.splitlines(), result.splitlines()[1:]):
            if line_a.startswith("# file:"):
                self.assertFalse(line_b.startswith("# file:"), "two consecutive file comments with no code between them")

    def test_all_symbols_from_same_file_grouped_together(self):
        # deep_chain: a, b, c, d all in one file — all code must appear under a single file section
        graph = Parser().trace(fixture("deep_chain.py"), "a")
        result = CodeSerializer().translate(graph)
        file_comment_pos = result.index("# file:")
        # all function defs must appear after the single file comment
        self.assertGreater(result.index("def d"), file_comment_pos)
        self.assertGreater(result.index("def a"), file_comment_pos)

    def test_symbols_within_file_section_in_dependency_order(self):
        # within the single file section, d must appear before a
        graph = Parser().trace(fixture("deep_chain.py"), "a")
        result = CodeSerializer().translate(graph)
        self.assertLess(result.index("def d"), result.index("def a"))


class TestJsonSerializerEdgeCases(unittest.TestCase):
    def test_circular_dependency_is_valid_json(self):
        graph = Parser().trace(fixture("circular.py"), "entry")
        result = json.loads(JsonSerializer().translate(graph))
        names = [k.split("::")[-1] for k in result]
        self.assertIn("ping", names)
        self.assertIn("pong", names)

    def test_async_function_type_is_function(self):
        graph = Parser().trace(fixture("async_func.py"), "async_uses_helper")
        result = json.loads(JsonSerializer().translate(graph))
        node = next(v for k, v in result.items() if k.endswith("::async_uses_helper"))
        self.assertEqual(node["type"], "function")

    def test_variable_with_dependency_in_json(self):
        graph = Parser().trace(fixture("simple.py"), "DEPENDENT_VAR")
        result = json.loads(JsonSerializer().translate(graph))
        node = next(v for k, v in result.items() if k.endswith("::DEPENDENT_VAR"))
        dep_names = [d.split("::")[-1] for d in node["dependencies"]]
        self.assertIn("MAX_SIZE", dep_names)

    def test_star_import_node_has_correct_file_path(self):
        graph = Parser().trace(fixture("star_all_import.py"), "uses_exported")
        result = json.loads(JsonSerializer().translate(graph))
        node = next(v for k, v in result.items() if k.endswith("::exported_func"))
        self.assertIn("star_all_source.py", node["file_path"])


class TestCodeSerializerFullOutput(unittest.TestCase):
    def test_simple_function_with_dependency(self):
        graph = Parser().trace(fixture("simple.py"), "uses_helper")
        result = CodeSerializer().translate(graph)
        expected = (
            "# file: tests/fixtures/simple.py\n"
            "def helper():\n"
            '    return "i am a helper"\n'
            "\n\n"
            "def uses_helper():\n"
            "    return helper()"
        )
        self.assertEqual(result, expected)

    def test_cross_file_dependency(self):
        graph = Parser().trace(fixture("cross_file_a.py"), "uses_imported_function")
        result = CodeSerializer().translate(graph)
        expected = (
            "# file: tests/fixtures/cross_file_b.py\n"
            "def shared_helper():\n"
            '    return "i am from another file"\n'
            "\n\n"
            "# file: tests/fixtures/cross_file_a.py\n"
            "def uses_imported_function():\n"
            "    return shared_helper()"
        )
        self.assertEqual(result, expected)

    def test_decorator_function(self):
        graph = Parser().trace(fixture("decorators.py"), "single_decorated")
        result = CodeSerializer().translate(graph)
        expected = (
            "# file: tests/fixtures/decorators.py\n"
            "def my_decorator(func):\n"
            "    return func\n"
            "\n\n"
            "@my_decorator\n"
            "def single_decorated():\n"
            '    return "decorated once"'
        )
        self.assertEqual(result, expected)

    def test_deep_chain(self):
        graph = Parser().trace(fixture("deep_chain.py"), "a")
        result = CodeSerializer().translate(graph)
        expected = (
            "# file: tests/fixtures/deep_chain.py\n"
            "def d():\n"
            '    return "end"\n'
            "\n\n"
            "def c():\n"
            "    return d()\n"
            "\n\n"
            "def b():\n"
            "    return c()\n"
            "\n\n"
            "def a():\n"
            "    return b()"
        )
        self.assertEqual(result, expected)

    def test_async_function(self):
        graph = Parser().trace(fixture("async_func.py"), "async_uses_helper")
        result = CodeSerializer().translate(graph)
        expected = (
            "# file: tests/fixtures/async_func.py\n"
            "async def async_helper():\n"
            '    return "async"\n'
            "\n\n"
            "async def async_uses_helper():\n"
            "    return await async_helper()"
        )
        self.assertEqual(result, expected)

    def test_variable_with_dependency(self):
        graph = Parser().trace(fixture("simple.py"), "DEPENDENT_VAR")
        result = CodeSerializer().translate(graph)
        expected = (
            "# file: tests/fixtures/simple.py\n"
            "MAX_SIZE = 100\n"
            "\n\n"
            "DEPENDENT_VAR = MAX_SIZE"
        )
        self.assertEqual(result, expected)

    def test_star_import_function(self):
        graph = Parser().trace(fixture("star_all_import.py"), "uses_exported")
        result = CodeSerializer().translate(graph)
        expected = (
            "# file: tests/fixtures/star_all_source.py\n"
            "def exported_func():\n"
            '    return "exported"\n'
            "\n\n"
            "# file: tests/fixtures/star_all_import.py\n"
            "def uses_exported():\n"
            "    return exported_func()"
        )
        self.assertEqual(result, expected)


class TestCodeSerializerMethods(unittest.TestCase):
    def test_animal_speak_full_output(self):
        graph = Parser().trace(fixture("classes.py"), "Animal.speak")
        result = CodeSerializer().translate(graph)
        expected = (
            "# file: tests/fixtures/classes.py\n"
            "def helper():\n"
            '    return "helper"\n'
            "\n\n"
            "class Animal:\n"
            '    sound = "generic"\n'
            "\n"
            "    def speak(self):\n"
            "        return helper()"
        )
        self.assertEqual(result, expected)

    def test_dog_fetch_full_output(self):
        graph = Parser().trace(fixture("classes.py"), "Dog.fetch")
        result = CodeSerializer().translate(graph)
        expected = (
            "# file: tests/fixtures/classes.py\n"
            "def helper():\n"
            '    return "helper"\n'
            "\n\n"
            "class Dog(Animal):\n"
            '    name = "Rex"\n'
            "\n"
            "    def speak(self):\n"
            "        return helper()\n"
            "\n"
            "    def fetch(self):\n"
            "        return self.speak()"
        )
        self.assertEqual(result, expected)

    def test_nested_class_full_output(self):
        graph = Parser().trace(fixture("classes.py"), "Outer.Inner.method")
        result = CodeSerializer().translate(graph)
        expected = (
            "# file: tests/fixtures/classes.py\n"
            "def helper():\n"
            '    return "helper"\n'
            "\n\n"
            "class Outer:\n"
            "    class Inner:\n"
            "        value = 42\n"
            "\n"
            "        def method(self):\n"
            "            return helper()"
        )
        self.assertEqual(result, expected)


class TestJsonSerializerFullOutput(unittest.TestCase):
    def _parse(self, fixture_name, name):
        graph = Parser().trace(fixture(fixture_name), name)
        return json.loads(JsonSerializer().translate(graph))

    def test_simple_function_with_dependency(self):
        result = self._parse("simple.py", "uses_helper")
        self.assertEqual(result, {
            "tests/fixtures/simple.py::uses_helper": {
                "type": "function",
                "file_path": "tests/fixtures/simple.py",
                "dependencies": ["tests/fixtures/simple.py::helper"],
            },
            "tests/fixtures/simple.py::helper": {
                "type": "function",
                "file_path": "tests/fixtures/simple.py",
                "dependencies": [],
            },
        })

    def test_cross_file_dependency(self):
        result = self._parse("cross_file_a.py", "uses_imported_function")
        self.assertEqual(result, {
            "tests/fixtures/cross_file_a.py::uses_imported_function": {
                "type": "function",
                "file_path": "tests/fixtures/cross_file_a.py",
                "dependencies": ["tests/fixtures/cross_file_b.py::shared_helper"],
            },
            "tests/fixtures/cross_file_b.py::shared_helper": {
                "type": "function",
                "file_path": "tests/fixtures/cross_file_b.py",
                "dependencies": [],
            },
        })

    def test_variable_with_dependency(self):
        result = self._parse("simple.py", "DEPENDENT_VAR")
        self.assertEqual(result, {
            "tests/fixtures/simple.py::DEPENDENT_VAR": {
                "type": "variable",
                "file_path": "tests/fixtures/simple.py",
                "dependencies": ["tests/fixtures/simple.py::MAX_SIZE"],
            },
            "tests/fixtures/simple.py::MAX_SIZE": {
                "type": "variable",
                "file_path": "tests/fixtures/simple.py",
                "dependencies": [],
            },
        })

    def test_async_function(self):
        result = self._parse("async_func.py", "async_uses_helper")
        self.assertEqual(result, {
            "tests/fixtures/async_func.py::async_uses_helper": {
                "type": "function",
                "file_path": "tests/fixtures/async_func.py",
                "dependencies": ["tests/fixtures/async_func.py::async_helper"],
            },
            "tests/fixtures/async_func.py::async_helper": {
                "type": "function",
                "file_path": "tests/fixtures/async_func.py",
                "dependencies": [],
            },
        })

    def test_star_import(self):
        result = self._parse("star_all_import.py", "uses_exported")
        self.assertEqual(result, {
            "tests/fixtures/star_all_import.py::uses_exported": {
                "type": "function",
                "file_path": "tests/fixtures/star_all_import.py",
                "dependencies": ["tests/fixtures/star_all_source.py::exported_func"],
            },
            "tests/fixtures/star_all_source.py::exported_func": {
                "type": "function",
                "file_path": "tests/fixtures/star_all_source.py",
                "dependencies": [],
            },
        })

    def test_class_method(self):
        result = self._parse("classes.py", "Animal.speak")
        self.assertEqual(result, {
            "tests/fixtures/classes.py::Animal.speak": {
                "type": "function",
                "file_path": "tests/fixtures/classes.py",
                "dependencies": [
                    "tests/fixtures/classes.py::Animal",
                    "tests/fixtures/classes.py::helper",
                ],
            },
            "tests/fixtures/classes.py::Animal": {
                "type": "class",
                "file_path": "tests/fixtures/classes.py",
                "dependencies": ["tests/fixtures/classes.py::helper"],
            },
            "tests/fixtures/classes.py::helper": {
                "type": "function",
                "file_path": "tests/fixtures/classes.py",
                "dependencies": [],
            },
        })

    def test_deep_chain(self):
        result = self._parse("deep_chain.py", "a")
        self.assertEqual(result, {
            "tests/fixtures/deep_chain.py::a": {
                "type": "function",
                "file_path": "tests/fixtures/deep_chain.py",
                "dependencies": ["tests/fixtures/deep_chain.py::b"],
            },
            "tests/fixtures/deep_chain.py::b": {
                "type": "function",
                "file_path": "tests/fixtures/deep_chain.py",
                "dependencies": ["tests/fixtures/deep_chain.py::c"],
            },
            "tests/fixtures/deep_chain.py::c": {
                "type": "function",
                "file_path": "tests/fixtures/deep_chain.py",
                "dependencies": ["tests/fixtures/deep_chain.py::d"],
            },
            "tests/fixtures/deep_chain.py::d": {
                "type": "function",
                "file_path": "tests/fixtures/deep_chain.py",
                "dependencies": [],
            },
        })


class TestJsonSerializerMethods(unittest.TestCase):
    def test_animal_speak_full_graph(self):
        graph = Parser().trace(fixture("classes.py"), "Animal.speak")
        result = json.loads(JsonSerializer().translate(graph))
        # normalize keys to just names
        by_name = {k.split("::")[-1]: v for k, v in result.items()}

        self.assertEqual(set(by_name.keys()), {"helper", "Animal", "Animal.speak"})
        self.assertEqual(by_name["Animal.speak"]["type"], "function")
        self.assertEqual(by_name["Animal"]["type"], "class")
        self.assertEqual(by_name["helper"]["type"], "function")
        self.assertIn(
            "Animal",
            [d.split("::")[-1] for d in by_name["Animal.speak"]["dependencies"]]
        )

    def test_dog_fetch_full_graph(self):
        graph = Parser().trace(fixture("classes.py"), "Dog.fetch")
        result = json.loads(JsonSerializer().translate(graph))
        by_name = {k.split("::")[-1]: v for k, v in result.items()}

        self.assertIn("Dog.fetch", by_name)
        self.assertIn("Dog.speak", by_name)
        self.assertIn("Dog", by_name)
        self.assertIn("helper", by_name)
        self.assertNotIn("Dog.sit", by_name)
        self.assertEqual(by_name["Dog.fetch"]["type"], "function")
        self.assertEqual(by_name["Dog"]["type"], "class")

    def test_nested_class_full_graph(self):
        graph = Parser().trace(fixture("classes.py"), "Outer.Inner.method")
        result = json.loads(JsonSerializer().translate(graph))
        by_name = {k.split("::")[-1]: v for k, v in result.items()}

        self.assertIn("Outer.Inner.method", by_name)
        self.assertIn("Outer.Inner", by_name)
        self.assertIn("helper", by_name)
        self.assertEqual(by_name["Outer.Inner"]["type"], "class")
        self.assertEqual(by_name["Outer.Inner.method"]["type"], "function")


if __name__ == "__main__":
    unittest.main()

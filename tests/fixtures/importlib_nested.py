import importlib


def outer():
    def inner():
        # importlib call is inside a nested function — should NOT bleed into outer's deps
        mod = importlib.import_module("tests.fixtures.cross_file_b")
        return mod.shared_helper()
    return inner()

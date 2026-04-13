import importlib


def uses_importlib():
    mod = importlib.import_module("tests.fixtures.cross_file_b")
    return mod.shared_helper()


def uses_importlib_from_import():
    from importlib import import_module
    mod = import_module("tests.fixtures.cross_file_b")
    return mod.shared_helper()

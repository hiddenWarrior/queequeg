from tests.fixtures.star_all_source import *


def uses_exported():
    return exported_func()


def uses_hidden():
    return hidden_func()

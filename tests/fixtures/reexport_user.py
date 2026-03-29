from tests.fixtures.reexport_pkg import *


def uses_reexported():
    return core_func()

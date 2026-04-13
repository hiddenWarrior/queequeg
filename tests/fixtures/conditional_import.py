import sys

if sys.version_info >= (3, 11):
    from tests.fixtures.cross_file_b import shared_helper
else:
    from tests.fixtures.cross_file_b import shared_helper

try:
    from tests.fixtures.cross_file_b import SharedClass
except ImportError:
    SharedClass = None


def uses_if_import():
    return shared_helper()


def uses_try_import():
    return SharedClass()

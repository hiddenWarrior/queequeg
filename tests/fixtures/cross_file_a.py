from tests.fixtures.cross_file_b import shared_helper, SharedClass


def uses_imported_function():
    return shared_helper()


def uses_imported_class():
    obj = SharedClass()
    return obj.greet()

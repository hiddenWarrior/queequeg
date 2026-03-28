def uses_inline_import():
    from tests.fixtures.cross_file_b import shared_helper
    return shared_helper()

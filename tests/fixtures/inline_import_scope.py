from tests.fixtures.cross_file_b import shared_helper


def helper():
    return "local helper"


def uses_inline_import():
    from tests.fixtures.cross_file_b import helper  # inline import shadows local helper
    return helper()


def uses_local_helper():
    return helper()  # should use local helper, not the inline import in uses_inline_import


# top-level import AFTER local definition — import should win
def local_helper_v2():
    return "local v2"


from tests.fixtures.cross_file_b import helper as local_helper_v2  # noqa


def uses_import_after_local_def():
    return local_helper_v2()

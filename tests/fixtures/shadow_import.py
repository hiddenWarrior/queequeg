from tests.fixtures.cross_file_b import shared_helper


def shared_helper():
    return "local override"


def uses_shadowed():
    return shared_helper()


# import AFTER local definition — import should win
def local_first():
    return "local"


from tests.fixtures.cross_file_b import shared_helper as local_first  # noqa


def uses_import_after_local():
    return local_first()

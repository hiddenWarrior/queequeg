from tests.fixtures.cross_file_b import shared_helper
from tests.fixtures.cross_file_b import helper


def dep_in_try_body():
    try:
        return shared_helper()
    except Exception:
        return None


def dep_in_except_body():
    try:
        pass
    except Exception:
        return helper()


def dep_in_finally_body():
    try:
        pass
    finally:
        return shared_helper()

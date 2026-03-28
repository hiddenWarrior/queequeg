from tests.fixtures.cross_file_b import *
from tests.fixtures.star_file_b import *


def uses_star_import():
    return shared_helper()


def uses_chained_star_import():
    return deep_helper()  # deep_helper lives in star_file_c, re-exported via star_file_b's *

from tests.fixtures.cross_file_b import shared_helper
from tests.fixtures.cross_file_b import helper


def uses_multiple_lambdas():
    # First lambda shadows shared_helper as param — never called outside
    f = lambda shared_helper: shared_helper * 2
    # Second lambda uses helper as free var
    g = lambda x: helper(x)
    return g(5)

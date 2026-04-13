from tests.fixtures.cross_file_b import helper


def uses_star_unpack():
    # *helper is the starred unpack target — shadows the import, should NOT be traced as dep
    first, *helper = [1, 2, 3, 4]
    return first

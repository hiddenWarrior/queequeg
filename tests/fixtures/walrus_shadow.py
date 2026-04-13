from tests.fixtures.cross_file_b import shared_helper


def get_data():
    return [1, 2, 3]


def uses_walrus():
    # walrus assigns to 'shared_helper' — shadows the import, should NOT be traced as dep
    if shared_helper := get_data():
        return shared_helper
    return []

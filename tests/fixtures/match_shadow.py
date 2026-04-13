from tests.fixtures.cross_file_b import shared_helper


def uses_match(value):
    # case binds 'shared_helper' — shadows the import, should NOT be traced as dep
    match value:
        case str() as shared_helper:
            return len(shared_helper)
        case _:
            return 0

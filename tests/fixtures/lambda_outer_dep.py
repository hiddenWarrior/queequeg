from tests.fixtures.cross_file_b import shared_helper


def uses_lambda_and_outer_import():
    # lambda param 'shared_helper' — but outer function also calls the import
    transform = lambda shared_helper: shared_helper * 2
    return shared_helper()  # genuine dep — should still be traced

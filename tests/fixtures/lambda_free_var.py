from tests.fixtures.cross_file_b import shared_helper


def uses_lambda_with_free_var():
    # shared_helper is NOT a lambda param — it's a free variable
    transform = lambda x: shared_helper(x)
    return transform(5)

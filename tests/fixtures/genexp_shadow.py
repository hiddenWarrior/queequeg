from tests.fixtures.cross_file_b import shared_helper


def uses_genexp_var():
    # shared_helper is only a generator expression iteration variable — NOT a dep
    result = list(shared_helper for shared_helper in range(10))
    return result

from tests.fixtures.cross_file_b import shared_helper


def uses_comp_var():
    # shared_helper is only used as a comprehension variable — NOT an outer dep
    result = [shared_helper for shared_helper in range(10)]
    return result

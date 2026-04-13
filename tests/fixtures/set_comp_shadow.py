from tests.fixtures.cross_file_b import shared_helper


def uses_set_comp_var():
    # shared_helper is only a set comprehension iteration variable — NOT a dep
    result = {shared_helper for shared_helper in range(10)}
    return result

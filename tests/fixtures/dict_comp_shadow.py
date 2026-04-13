from tests.fixtures.cross_file_b import shared_helper


def uses_dict_comp_var():
    # shared_helper is only a dict comprehension iteration variable — NOT a dep
    result = {shared_helper: shared_helper * 2 for shared_helper in range(10)}
    return result

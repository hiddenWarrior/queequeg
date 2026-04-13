from tests.fixtures.cross_file_b import shared_helper


def uses_comp_with_free_var():
    # shared_helper is a free variable inside the comprehension (NOT the iter var)
    result = [shared_helper(x) for x in range(10)]
    return result

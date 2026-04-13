from tests.fixtures.cross_file_b import shared_helper


def uses_multi_gen_comp():
    # row and x are both iter vars — NOT deps
    # shared_helper is a free variable — IS a dep
    result = [shared_helper(x) for row in [[1, 2], [3, 4]] for x in row]
    return result


def uses_nested_comp():
    # outer iter var 'row', inner iter var 'x' — both NOT deps
    # shared_helper is free var — IS a dep
    result = [[shared_helper(x) for x in row] for row in [[1, 2], [3, 4]]]
    return result

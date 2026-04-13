from tests.fixtures.cross_file_b import shared_helper


def comp_var_then_outer_call():
    # shared_helper used as comp iter var (shadowed inside comp)
    filtered = [shared_helper for shared_helper in range(10)]
    # shared_helper also called directly outside the comp — this IS a real dep
    return shared_helper()

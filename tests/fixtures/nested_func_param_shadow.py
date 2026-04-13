from tests.fixtures.cross_file_b import shared_helper


def outer_with_nested_param():
    # inner's param shadows the outer import — outer never uses the import directly
    def inner(shared_helper):
        return shared_helper * 2
    return inner(42)


def outer_with_nested_free_var():
    # inner uses shared_helper as a free variable — IS a dep of outer
    def inner():
        return shared_helper()
    return inner()

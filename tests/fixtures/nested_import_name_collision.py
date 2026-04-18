from tests.fixtures.cross_file_b import shared_helper as target_func


def outer():
    def inner():
        from tests.fixtures.cross_file_b import helper as target_func  # same local name as outer
        return target_func()
    inner()
    return target_func()  # should resolve to shared_helper

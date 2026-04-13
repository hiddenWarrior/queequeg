from tests.fixtures.cross_file_b import shared_helper as target_func


def outer_uses_import():
    def inner():
        # this import should NOT bleed into outer_uses_import's effective import map
        from tests.fixtures.cross_file_b import helper as target_func
        return target_func()
    return target_func()  # should resolve to shared_helper, not helper

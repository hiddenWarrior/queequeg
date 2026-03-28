def outer():
    def inner():
        from tests.fixtures.cross_file_b import shared_helper
        return shared_helper()
    return inner()


class MyClass:
    def method(self):
        def inner():
            from tests.fixtures.cross_file_b import shared_helper
            return shared_helper()
        return inner()

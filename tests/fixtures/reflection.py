import tests.fixtures.cross_file_b as cfb


class ReflectionClass:
    def method_a(self):
        return "a"

    def call_via_getattr(self):
        return getattr(self, "method_a")()

    def access_via_getattr(self):
        # accessed but not called — still a dependency
        return getattr(self, "method_a")

    def getattr_with_default(self):
        # 3-arg form
        return getattr(self, "method_a", None)

    def getattr_dynamic(self, name):
        # variable attr — unresolvable, should not crash
        return getattr(self, name)


def access_imported_attr():
    # getattr on an imported module, not called
    return getattr(cfb, "shared_helper")

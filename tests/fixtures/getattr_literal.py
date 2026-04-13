import tests.fixtures.cross_file_b as cfb


class Dispatcher:
    def handle_a(self):
        return "result"

    def dispatch_literal(self):
        return getattr(self, "handle_a")()

    def dispatch_dynamic(self, action):
        return getattr(self, action)()


def calls_via_getattr():
    return getattr(cfb, "shared_helper")()

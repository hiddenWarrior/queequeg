from tests.fixtures.constructor_dep import MyService


class Builder:
    def build(self):
        return MyService()

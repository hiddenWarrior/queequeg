from tests.fixtures.cross_file_b import SharedClass


class Child(SharedClass):
    def greet(self):
        return "child: " + super().greet()

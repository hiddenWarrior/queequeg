def helper_a():
    return 1


def helper_b():
    return 2


class A:
    def compute(self):
        return helper_a()


class B:
    def compute(self):
        return helper_b()


class C(A, B):
    def compute(self):
        return super().compute()

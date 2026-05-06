from tests.fixtures.callee import callee_func


def calls_callee():
    return callee_func()


def does_not_call_callee():
    return "unrelated"

MAX_SIZE = 100
PREFIX: str = "hello"


def standalone():
    return "i have no dependencies"


def helper():
    return "i am a helper"


def uses_helper():
    return helper()


def uses_global():
    return MAX_SIZE


def uses_global_and_helper():
    if MAX_SIZE > 0:
        return helper()


def shadows_global():
    MAX_SIZE = 999
    return MAX_SIZE


def uses_global_explicitly():
    global MAX_SIZE
    MAX_SIZE = 999
    return MAX_SIZE


def shadows_with_for_loop():
    for helper in range(10):
        pass
    return helper


def shadows_with_arg(helper):
    return helper


def shadows_with_varargs(*helper, **MAX_SIZE):
    return helper, MAX_SIZE


def shadows_with_tuple_unpack():
    helper, other = 1, 2
    return helper


def shadows_with_context_manager():
    with open(__file__) as helper:
        pass
    return helper


def shadows_with_except():
    try:
        pass
    except Exception as helper:
        pass


def shadows_with_inner_function():
    def helper():
        return "inner"
    return helper()


def uses_helper_in_default_arg(x=helper()):
    return x


def outer_with_nonlocal():
    helper = "not the module helper"
    def inner():
        nonlocal helper
        helper = "modified"
    inner()
    return helper


def shadows_with_for_tuple():
    for helper, other in [(1, 2)]:
        pass


def shadows_with_multiple_context_managers():
    with open(__file__) as helper, open(__file__) as MAX_SIZE:
        pass


DEPENDENT_VAR = MAX_SIZE

def func_one():
    return "one"


def func_two():
    return "two"


def func_three():
    return "three"


def func_hidden():
    return "not exported"


__all__ = ['func_one'] + ['func_two']
__all__ += ['func_three']

def my_decorator(func):
    return func


def another_decorator(arg):
    def wrapper(func):
        return func
    return wrapper


@my_decorator
def single_decorated():
    return "decorated once"


@my_decorator
@another_decorator("arg")
def multi_decorated():
    return "decorated twice"


@another_decorator(
    "multiline"
)
def multiline_decorated():
    return "multiline decorator"


@my_decorator
class DecoratedClass:
    pass

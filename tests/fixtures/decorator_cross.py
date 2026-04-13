from tests.fixtures.decorators import my_decorator, another_decorator


@my_decorator
def uses_imported_decorator():
    return "decorated from another file"


@another_decorator("arg")
def uses_factory_decorator():
    return "factory decorated from another file"

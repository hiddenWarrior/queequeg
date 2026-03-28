__all__ = ['exported_func']


def exported_func():
    return "exported"


def hidden_func():
    return "not exported via __all__"

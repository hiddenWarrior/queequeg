def shared_helper():
    return "i am from another file"


def helper():
    return "i am helper from another file"


class SharedClass:
    def greet(self):
        return "hello from SharedClass"

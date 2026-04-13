class NoInit:
    def greet(self):
        return "hi"


def creates_no_init():
    obj = NoInit()
    return obj.greet()

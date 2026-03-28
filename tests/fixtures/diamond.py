def shared():
    return "shared"


def left():
    return shared()


def right():
    return shared()


def top():
    return left() + right()

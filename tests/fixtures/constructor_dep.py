def init_helper():
    return 42


class MyService:
    def __init__(self):
        self.value = init_helper()

    def get_value(self):
        return self.value


def creates_service():
    svc = MyService()
    return svc.get_value()

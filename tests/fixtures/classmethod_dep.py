def standalone_helper():
    return "helped"


class MyClass:
    @classmethod
    def create(cls):
        return cls.process()

    @classmethod
    def process(cls):
        return standalone_helper()

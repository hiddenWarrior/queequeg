class MyModel:
    def process(self):
        return 1


def annotated_param(x: MyModel):
    pass


def annotated_return() -> MyModel:
    pass

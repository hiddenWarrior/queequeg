class MyModel:
    def process(self):
        return 1


def uses_string_annotation(x: "MyModel"):
    pass


def uses_real_annotation(x: MyModel):
    pass

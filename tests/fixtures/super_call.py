def base_helper():
    return 1


class Base:
    def compute(self):
        return base_helper()


class Child(Base):
    def compute(self):
        base_result = super().compute()
        return base_result + 1

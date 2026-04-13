class CompClass:
    def method_with_self_in_comp(self):
        # self.transform() called inside list comp body — should trace CompClass.transform
        result = [self.transform(x) for x in range(10)]
        return result

    def method_with_getattr_in_comp(self):
        # getattr(self, "transform") inside comp — should trace CompClass.transform
        result = [getattr(self, "transform")(x) for x in range(10)]
        return result

    def transform(self, x):
        return x * 2

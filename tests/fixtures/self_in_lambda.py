class LambdaClass:
    def method_with_self_in_lambda(self):
        # self.helper() called inside lambda body — should still trace LambdaClass.helper
        transform = lambda x: self.helper(x)
        return transform(5)

    def helper(self, x):
        return x * 2

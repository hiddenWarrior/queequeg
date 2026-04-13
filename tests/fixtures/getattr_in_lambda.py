class GetAttrLambdaClass:
    def method_with_getattr_in_lambda(self):
        # getattr(self, "helper") inside lambda body — should trace GetAttrLambdaClass.helper
        dispatch = lambda: getattr(self, "helper")()
        return dispatch()

    def helper(self):
        return 42

def helper():
    return "helper"


class Animal:
    sound = "generic"

    def speak(self):
        return helper()

    def sleep(self):
        return "zzz"


class Dog(Animal):
    name = "Rex"

    def speak(self):
        return helper()

    def fetch(self):
        return self.speak()

    def sit(self):
        return "sitting"


class Outer:
    class Inner:
        value = 42

        def method(self):
            return helper()

    def outer_method(self):
        return self.Inner().method()

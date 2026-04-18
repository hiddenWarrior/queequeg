def compute_price():
    return 9.99


class Product:
    @property
    def price(self):
        return compute_price()

    @property
    def label(self):
        return f"${self.price}"

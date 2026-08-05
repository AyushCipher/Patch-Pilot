class ProductStore:
    """The source of truth for base (pre-tax) product prices."""

    def __init__(self):
        self._products = {}

    def set_price(self, sku: str, price: float) -> None:
        self._products[sku] = price

    def get_price(self, sku: str) -> float:
        return self._products.get(sku)

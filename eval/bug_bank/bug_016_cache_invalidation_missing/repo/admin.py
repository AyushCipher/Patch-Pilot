class PriceAdmin:
    def __init__(self, store, cache):
        self.store = store
        self.cache = cache

    def update_price(self, sku: str, new_price: float) -> None:
        """Update a product's base price. Callers must see the new display
        price immediately after this returns."""
        self.store.set_price(sku, new_price)

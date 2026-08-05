class PriceCache:
    """Caches computed display prices (base + tax) per SKU. Must be
    invalidated whenever the underlying base price changes, via invalidate()."""

    def __init__(self, store):
        self.store = store
        self._cache = {}

    def display_price(self, sku: str, tax_rate: float) -> float:
        if sku in self._cache:
            return self._cache[sku]
        base = self.store.get_price(sku)
        display = round(base * (1 + tax_rate), 2)
        self._cache[sku] = display
        return display

    def invalidate(self, sku: str) -> None:
        self._cache.pop(sku, None)

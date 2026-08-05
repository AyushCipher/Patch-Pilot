from memory_cache import MemoryCache


class PricingService:
    def __init__(self):
        self.cache = MemoryCache()

    def get_price(self, sku, compute_fn):
        cached = self.cache.get(sku)
        if cached is not None:
            return cached
        price = compute_fn(sku)
        self.cache.set(sku, price)
        return price

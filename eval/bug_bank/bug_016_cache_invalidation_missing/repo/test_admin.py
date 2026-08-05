from product_store import ProductStore
from price_cache import PriceCache
from admin import PriceAdmin


def test_price_update_reflected_immediately():
    store = ProductStore()
    store.set_price("SKU1", 100)
    cache = PriceCache(store)
    admin = PriceAdmin(store, cache)

    assert cache.display_price("SKU1", 0.10) == 110.0

    admin.update_price("SKU1", 200)

    assert cache.display_price("SKU1", 0.10) == 220.0


def test_uncached_sku_unaffected():
    store = ProductStore()
    store.set_price("SKU2", 50)
    cache = PriceCache(store)
    admin = PriceAdmin(store, cache)

    admin.update_price("SKU2", 60)

    assert cache.display_price("SKU2", 0.0) == 60.0

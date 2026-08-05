from pricing_service import PricingService


def test_computes_and_caches_on_first_miss():
    calls = []

    def compute(sku):
        calls.append(sku)
        return 42

    service = PricingService()
    assert service.get_price("SKU1", compute) == 42
    assert service.get_price("SKU1", compute) == 42
    assert calls == ["SKU1"]


def test_different_skus_computed_independently():
    calls = []

    def compute(sku):
        calls.append(sku)
        return len(sku)

    service = PricingService()
    assert service.get_price("A", compute) == 1
    assert service.get_price("BB", compute) == 2
    assert calls == ["A", "BB"]

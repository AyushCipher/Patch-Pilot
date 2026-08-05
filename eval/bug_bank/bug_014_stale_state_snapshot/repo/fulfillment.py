class FulfillmentService:
    """Checks whether an order can currently be fulfilled from stock."""

    def __init__(self, ledger):
        self.stock_snapshot = dict(ledger.stock)

    def can_fulfill(self, sku: str, qty: int) -> bool:
        return self.stock_snapshot.get(sku, 0) >= qty

class InventoryLedger:
    """The single source of truth for stock levels. Other services must
    read through this ledger rather than caching their own copy of the
    stock levels, since reservations mutate it over time."""

    def __init__(self, stock: dict):
        self.stock = stock

    def available(self, sku: str) -> int:
        return self.stock.get(sku, 0)

    def reserve(self, sku: str, qty: int) -> None:
        if self.available(sku) < qty:
            raise ValueError(f"insufficient stock for {sku}")
        self.stock[sku] -= qty

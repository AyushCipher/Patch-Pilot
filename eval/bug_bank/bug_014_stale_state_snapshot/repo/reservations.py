from ledger import InventoryLedger


class ReservationService:
    def __init__(self, ledger: InventoryLedger):
        self.ledger = ledger
        self.pending = {}

    def reserve(self, order_id: str, sku: str, qty: int) -> None:
        self.ledger.reserve(sku, qty)
        self.pending[order_id] = (sku, qty)

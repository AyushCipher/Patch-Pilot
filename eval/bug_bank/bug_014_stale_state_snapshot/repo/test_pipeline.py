from ledger import InventoryLedger
from reservations import ReservationService
from fulfillment import FulfillmentService


def test_fulfillment_reflects_reservations():
    ledger = InventoryLedger({"WIDGET": 10})
    fulfillment = FulfillmentService(ledger)
    reservations = ReservationService(ledger)

    reservations.reserve("order-1", "WIDGET", 7)

    assert fulfillment.can_fulfill("WIDGET", 3) is True
    assert fulfillment.can_fulfill("WIDGET", 4) is False


def test_fulfillment_before_any_reservation():
    ledger = InventoryLedger({"GADGET": 5})
    fulfillment = FulfillmentService(ledger)
    assert fulfillment.can_fulfill("GADGET", 5) is True

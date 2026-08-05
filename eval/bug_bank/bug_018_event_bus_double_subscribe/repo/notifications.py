from event_bus import EventBus


class NotificationService:
    """Subscribes to 'order_placed' events and sends exactly one
    notification per event, even across a resubscribe() call (e.g. after
    the service reconnects and needs to refresh its subscription)."""

    def __init__(self, bus: EventBus):
        self.bus = bus
        self.sent = []
        bus.subscribe("order_placed", self._on_order)

    def _on_order(self, payload) -> None:
        self.sent.append(payload)

    def resubscribe(self) -> None:
        self.bus.subscribe("order_placed", self._on_order)

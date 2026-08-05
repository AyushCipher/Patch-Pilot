from event_bus import EventBus
from notifications import NotificationService


def test_resubscribe_does_not_duplicate_handler():
    bus = EventBus()
    service = NotificationService(bus)
    service.resubscribe()

    bus.publish("order_placed", {"id": 1})

    assert service.sent == [{"id": 1}]


def test_publish_without_resubscribe_fires_once():
    bus = EventBus()
    service = NotificationService(bus)

    bus.publish("order_placed", {"id": 2})

    assert service.sent == [{"id": 2}]

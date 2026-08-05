class EventBus:
    def __init__(self):
        self._subscribers = {}

    def subscribe(self, event_name: str, handler) -> None:
        self._subscribers.setdefault(event_name, []).append(handler)

    def unsubscribe(self, event_name: str, handler) -> None:
        handlers = self._subscribers.get(event_name, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, event_name: str, payload) -> None:
        for handler in list(self._subscribers.get(event_name, [])):
            handler(payload)

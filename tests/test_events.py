from app.agent.events import EventBus, EventType


def test_event_bus_publish():
    bus = EventBus()
    received = []
    bus.subscribe(EventType.RESPONSE, received.append)

    event = bus.publish(EventType.RESPONSE, text="hello")

    assert event.type == EventType.RESPONSE
    assert event.data["text"] == "hello"
    assert len(received) == 1


def test_event_bus_unsubscribe():
    bus = EventBus()
    received = []
    handler = received.append
    bus.subscribe(EventType.RESPONSE, handler)
    bus.unsubscribe(EventType.RESPONSE, handler)
    bus.publish(EventType.RESPONSE, text="hello")
    assert received == []

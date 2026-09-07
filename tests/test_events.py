"""Tests for the JARVIS event bus."""

from app.agent.events import EventBus, EventType


def test_event_bus_publish_and_drain():
    bus = EventBus()

    bus.publish(
        EventType.USER_TEXT,
        text="hello",
    )

    events = bus.drain()

    assert len(events) == 1
    assert events[0].type == EventType.USER_TEXT
    assert events[0].data["text"] == "hello"


def test_event_bus_dispatch():
    bus = EventBus()

    received = []

    def callback(event):
        received.append(event)

    bus.subscribe(
        EventType.RESPONSE,
        callback,
    )

    bus.publish(
        EventType.RESPONSE,
        text="hello",
    )

    dispatched = bus.dispatch()

    assert dispatched == 1
    assert len(received) == 1
    assert received[0].data["text"] == "hello"


def test_event_bus_unsubscribe():
    bus = EventBus()

    received = []

    def callback(event):
        received.append(event)

    bus.subscribe(
        EventType.RESPONSE,
        callback,
    )

    bus.unsubscribe(
        EventType.RESPONSE,
        callback,
    )

    bus.publish(
        EventType.RESPONSE,
        text="hello",
    )

    bus.dispatch()

    assert received == []
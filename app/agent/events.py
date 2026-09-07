"""Central thread-safe event system for JARVIS."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Any, Callable


class EventType(str, Enum):
    USER_TEXT = "user_text"
    WAKE_WORD = "wake_word"
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    THINKING_START = "thinking_start"
    THINKING_END = "thinking_end"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    RESPONSE = "response"
    SPEAKING_START = "speaking_start"
    SPEAKING_END = "speaking_end"
    ERROR = "error"
    LISTENING_STARTED = "listening_started"
    LISTENING_STOPPED = "listening_stopped"
    HEALTH_CHECK = "health_check"


@dataclass
class Event:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


EventHandler = Callable[[Event], None]


class EventBus:
    """Thread-safe publish/subscribe event bus."""

    def __init__(self):
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._lock = Lock()

    def subscribe(self, event_type: EventType, handler: EventHandler):
        with self._lock:
            self._handlers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler):
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

    def publish(self, event_type: EventType, **data: Any) -> Event:
        event = Event(event_type, data)
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                continue
        return event

    def clear(self):
        with self._lock:
            self._handlers.clear()


_default_bus = EventBus()


def get_event_bus() -> EventBus:
    return _default_bus

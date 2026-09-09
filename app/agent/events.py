"""Thread-safe event bus used by JARVIS components."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from queue import Empty, Queue
from threading import RLock
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
    VOICE_STATE = "voice_state"

    HEALTH_CHECK = "health_check"

    TASK_STARTED = "task_started"
    TASK_FINISHED = "task_finished"
    TASK_FAILED = "task_failed"


@dataclass
class Event:
    """An event emitted by a JARVIS component."""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """Thread-safe publish/subscribe event bus."""

    def __init__(self):
        self._subscribers: dict[EventType, list[Callable[[Event], None]]] = {}
        self._queue: Queue[Event] = Queue()
        self._lock = RLock()

    def subscribe(
        self,
        event_type: EventType,
        callback: Callable[[Event], None],
    ) -> None:
        with self._lock:
            callbacks = self._subscribers.setdefault(event_type, [])

            if callback not in callbacks:
                callbacks.append(callback)

    def unsubscribe(
        self,
        event_type: EventType,
        callback: Callable[[Event], None],
    ) -> None:
        with self._lock:
            callbacks = self._subscribers.get(event_type, [])

            if callback in callbacks:
                callbacks.remove(callback)

    def publish(
        self,
        event_type: EventType,
        **data: Any,
    ) -> None:
        event = Event(
            type=event_type,
            data=data,
        )

        self._queue.put(event)

    def drain(self, limit: int = 100) -> list[Event]:
        """Return queued events without invoking callbacks."""
        events: list[Event] = []

        for _ in range(max(1, limit)):
            try:
                events.append(self._queue.get_nowait())
            except Empty:
                break

        return events

    def dispatch(self, limit: int = 100) -> int:
        """Dispatch queued events to subscribers."""
        events = self.drain(limit)

        for event in events:
            with self._lock:
                callbacks = list(
                    self._subscribers.get(event.type, [])
                )

            for callback in callbacks:
                try:
                    callback(event)
                except Exception:
                    # One broken subscriber must never kill the event bus.
                    continue

        return len(events)

    def clear(self) -> None:
        """Remove queued events."""
        self.drain(limit=100000)

    def clear_subscribers(self) -> None:
        with self._lock:
            self._subscribers.clear()


_global_event_bus = EventBus()


def get_event_bus() -> EventBus:
    """Return the global JARVIS event bus."""
    return _global_event_bus

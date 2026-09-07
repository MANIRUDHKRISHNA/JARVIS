"""Push-to-talk wake-word interface for JARVIS."""

from __future__ import annotations

import threading


class WakeWord:
    """Explicit activation controller; not an always-listening detector."""

    def __init__(self, wake_word: str = "jarvis"):
        self.wake_word = wake_word.lower()
        self.active = False
        self._lock = threading.Lock()

    def activate(self):
        with self._lock:
            self.active = True

    def deactivate(self):
        with self._lock:
            self.active = False

    def is_active(self) -> bool:
        with self._lock:
            return self.active

    def matches(self, text: str) -> bool:
        return self.wake_word in text.lower()


WakeWordDetector = WakeWord

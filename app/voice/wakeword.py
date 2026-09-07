"""Push-to-talk wake-word interface for JARVIS."""

from __future__ import annotations

class WakeWord:
    """Detect and extract commands following the configured wake word."""

    def __init__(self, wake_word: str = "jarvis"):
        self.wake_word = wake_word.lower().strip()

    def matches(self, text: str) -> bool:
        return bool(text) and self.wake_word in text.lower()

    def extract_command(self, text: str) -> str:
        if not text:
            return ""
        position = text.lower().find(self.wake_word)
        if position == -1:
            return ""
        return text[position + len(self.wake_word):].strip()


WakeWordDetector = WakeWord

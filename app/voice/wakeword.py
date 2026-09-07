"""Push-to-talk wake-word interface for JARVIS."""

from __future__ import annotations

class WakeWord:
    """Detect and extract commands following the configured wake word."""

    def __init__(self, wake_word: str | list[str] = "jarvis"):
        if isinstance(wake_word, list):
            self.wake_words = [word.lower().strip() for word in wake_word if word.strip()]
            self.wake_word = self.wake_words[0] if self.wake_words else "jarvis"
        else:
            self.wake_word = wake_word.lower().strip()
            self.wake_words = [self.wake_word]

    def matches(self, text: str) -> bool:
        return bool(text) and any(word in text.lower() for word in self.wake_words)

    def extract_command(self, text: str) -> str:
        if not text:
            return ""
        position = min(
            (text.lower().find(word), word)
            for word in self.wake_words
            if text.lower().find(word) != -1
        )[0] if any(word in text.lower() for word in self.wake_words) else -1
        if position == -1:
            return ""
        word = next(word for word in self.wake_words if text.lower().find(word) == position)
        return text[position + len(word):].strip()

    def detect(self, text: str) -> bool:
        return self.matches(text)

    def remove(self, text: str) -> str:
        return self.extract_command(text)


WakeWordDetector = WakeWord

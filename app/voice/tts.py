"""Local Windows text-to-speech."""

from __future__ import annotations

import pyttsx3
from threading import RLock


class TextToSpeech:
    """Windows local speech output."""

    def __init__(self):
        self.engine = pyttsx3.init()
        self._lock = RLock()
        self.engine.setProperty("rate", 175)
        self.engine.setProperty("volume", 1.0)

    def speak(self, text: str):
        if text:
            with self._lock:
                self.engine.say(text)
                self.engine.runAndWait()

    def stop(self):
        with self._lock:
            self.engine.stop()

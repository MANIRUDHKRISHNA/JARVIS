"""Background voice listener."""

from __future__ import annotations

import threading
import time


class VoiceListener:
    """Optional background listener with explicit wake-word filtering."""

    def __init__(self, voice_assistant, wake_word: str = "jarvis"):
        self.voice_assistant = voice_assistant
        self.wake_word = wake_word.lower()
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _run(self):
        while self.running:
            try:
                text = self.voice_assistant.listen_once(3)
                if not text or self.wake_word not in text.lower():
                    continue
                self.voice_assistant.process_voice(seconds=5)
            except Exception:
                time.sleep(1)

"""Background always-on JARVIS voice engine."""

from __future__ import annotations

import threading
import time

import numpy as np

from app.voice.microphone import Microphone
from app.voice.vad import VoiceActivityDetector


class BackgroundVoice:
    """Continuously listen for speech, then filter on the JARVIS wake word."""

    def __init__(self, voice_assistant, sample_rate: int = 16000):
        self.voice_assistant = voice_assistant
        self.microphone = Microphone(sample_rate=sample_rate)
        self.vad = VoiceActivityDetector()
        self.running = False
        self.thread = None
        self.on_status = None

    def start(self):
        if self.running:
            return
        self.running = True
        try:
            self.microphone.start()
        except Exception:
            self.running = False
            raise
        self.thread = threading.Thread(target=self._run, daemon=True, name="JARVIS-Voice")
        self.thread.start()
        self._status("Listening")

    def stop(self):
        self.running = False
        self.microphone.stop()
        self._status("Stopped")

    def _status(self, message: str):
        if self.on_status:
            try:
                self.on_status(message)
            except Exception:
                pass

    def _collect_audio(self, first_block, max_seconds: float = 8.0):
        blocks = [first_block]
        started = time.monotonic()
        while self.running and time.monotonic() - started < max_seconds:
            block = self.microphone.read(timeout=0.5)
            if len(block):
                blocks.append(block)
        return np.concatenate(blocks)

    def _run(self):
        while self.running:
            try:
                block = self.microphone.read(timeout=1.0)
                if not len(block) or not self.vad.is_speech(block):
                    continue
                self._status("Processing voice")
                text = self.voice_assistant.listen_once(self._collect_audio(block))
                if not text:
                    self._status("Listening")
                    continue
                self._status(f"Heard: {text}")
                if not self.voice_assistant.wakeword.matches(text):
                    self._status("Listening")
                    continue
                self._status("Command detected")
                self.voice_assistant.process_text(text)
                self._status("Listening")
            except Exception as exc:
                self._status(f"Voice error: {exc}")
                time.sleep(1)

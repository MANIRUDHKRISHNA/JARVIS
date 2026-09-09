"""Command audio capture for JARVIS."""

from __future__ import annotations

import time

import numpy as np

from app.voice.microphone import Microphone
from app.voice.vad import VoiceActivityDetector


class CommandCapture:
    """Capture one spoken command using the existing microphone and VAD."""

    def __init__(
        self,
        microphone: Microphone,
        vad: VoiceActivityDetector,
        *,
        min_speech_duration: float = 0.25,
        silence_timeout: float = 0.8,
        max_command_duration: float = 10.0,
    ):
        self.microphone = microphone
        self.vad = vad
        self.min_speech_duration = min_speech_duration
        self.silence_timeout = silence_timeout
        self.max_command_duration = max_command_duration

    def capture(self, cancelled=None) -> np.ndarray:
        """Capture one spoken command and return its audio."""

        chunks: list[np.ndarray] = []

        capture_started_at = time.monotonic()
        speech_started_at: float | None = None
        last_speech_at: float | None = None

        while True:
            if cancelled is not None and cancelled.is_set():
                raise InterruptedError("Command capture was cancelled.")
            frame = self.microphone.read(timeout=1.0)

            if frame.size == 0:
                if time.monotonic() - capture_started_at >= self.max_command_duration:
                    raise TimeoutError("No speech detected.")
                continue

            now = time.monotonic()
            is_speech = self.vad.is_speech(frame)

            if is_speech:
                if speech_started_at is None:
                    speech_started_at = now

                last_speech_at = now
                chunks.append(frame)

            elif speech_started_at is not None:
                # Keep trailing silence so STT receives a natural endpoint.
                chunks.append(frame)

            # Nothing has been said yet.
            if speech_started_at is None:
                if now - capture_started_at >= self.max_command_duration:
                    raise TimeoutError("No speech detected.")

                continue

            # Maximum command duration.
            if now - speech_started_at >= self.max_command_duration:
                break

            # Speech has stopped.
            if (
                last_speech_at is not None
                and now - last_speech_at >= self.silence_timeout
                and now - speech_started_at >= self.min_speech_duration
            ):
                break

        return self.microphone.combine(chunks)

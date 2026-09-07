"""Background voice engine."""

from __future__ import annotations

import threading

from app.agent.events import EventType, get_event_bus
from app.agent.logging import get_logger
from app.voice.assistant import VoiceAssistant
from app.voice.microphone import Microphone
from app.voice.stt import SpeechToText
from app.voice.vad import VoiceActivityDetector
from app.voice.wakeword import WakeWordDetector


class BackgroundVoiceEngine:
    """Continuously listens for speech and routes it to JARVIS."""

    def __init__(
        self,
        assistant: VoiceAssistant,
        microphone: Microphone | None = None,
        stt: SpeechToText | None = None,
        vad: VoiceActivityDetector | None = None,
        wakeword: WakeWordDetector | None = None,
    ):
        self.assistant = assistant

        self.microphone = microphone or Microphone()
        self.stt = stt or SpeechToText()
        self.vad = vad or VoiceActivityDetector()
        self.wakeword = wakeword or WakeWordDetector()

        self.events = get_event_bus()
        self.logger = get_logger()

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start background voice processing."""

        if self._running:
            return

        self._stop_event.clear()

        self.microphone.start()

        self._running = True

        self._thread = threading.Thread(
            target=self._loop,
            name="JARVIS-Voice",
            daemon=True,
        )

        self._thread.start()

        self.events.publish(
            EventType.LISTENING_STARTED,
        )

        self.logger.info(
            "Background voice engine started."
        )

    def stop(self) -> None:
        """Stop background voice processing."""

        if not self._running:
            return

        self._stop_event.set()

        try:
            self.microphone.stop()
        except Exception:
            self.logger.exception(
                "Microphone stop failed."
            )

        if (
            self._thread
            and self._thread.is_alive()
            and self._thread is not threading.current_thread()
        ):
            self._thread.join(timeout=3)

        self._thread = None
        self._running = False

        self.events.publish(
            EventType.LISTENING_STOPPED,
        )

        self.logger.info(
            "Background voice engine stopped."
        )

    def _loop(self) -> None:
        """Background microphone loop."""

        while not self._stop_event.is_set():
            try:
                audio = self.microphone.read(
                    timeout=0.5
                )
            except Exception as exc:
                self.logger.warning(
                    "Microphone read error: %s",
                    exc,
                )
                continue

            if audio is None:
                continue

            if not self.vad.is_speech(audio):
                continue

            self.events.publish(
                EventType.SPEECH_START,
            )

            chunks = [audio]
            silence_count = 0

            while (
                not self._stop_event.is_set()
                and silence_count < 5
            ):
                try:
                    chunk = self.microphone.read(
                        timeout=0.5
                    )
                except Exception:
                    break

                if chunk is None:
                    continue

                chunks.append(chunk)

                if self.vad.is_speech(chunk):
                    silence_count = 0
                else:
                    silence_count += 1

            self.events.publish(
                EventType.SPEECH_END,
            )

            if self._stop_event.is_set():
                break

            try:
                audio_data = self.microphone.combine(
                    chunks
                )

                text = self.stt.transcribe(
                    audio_data
                ).strip()

                if not text:
                    continue

                self.logger.info(
                    "Voice transcription: %s",
                    text,
                )

                detected, command = (
                    self.wakeword.detect_and_remove(text)
                )

                if not detected:
                    continue

                self.events.publish(
                    EventType.WAKE_WORD,
                    text=text,
                )

                if not command:
                    continue

                self.assistant.process_text(
                    command,
                    speak=True,
                )

            except Exception:
                self.logger.exception(
                    "Background voice processing failed."
                )


# Compatibility alias.
#
# Older parts of the voice package import BackgroundVoice.
# The current implementation is BackgroundVoiceEngine, so
# both names intentionally refer to the same implementation.
BackgroundVoice = BackgroundVoiceEngine

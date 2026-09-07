"""Voice interface for JARVIS."""

from __future__ import annotations

from threading import RLock

from app.agent.events import EventType, get_event_bus
from app.agent.logging import get_logger
from app.agent.pipeline import AgentPipeline
from app.voice.tts import TextToSpeech


class VoiceAssistant:
    """Connects speech input/output to the shared agent pipeline."""

    def __init__(
        self,
        pipeline: AgentPipeline | None = None,
        tts: TextToSpeech | None = None,
    ):
        self.pipeline = pipeline or AgentPipeline()
        self.tts = tts or TextToSpeech()

        self.events = get_event_bus()
        self.logger = get_logger()

        self._speak_lock = RLock()

    def process_text(
        self,
        text: str,
        speak: bool = True,
    ) -> str:
        """Process transcribed speech through the shared pipeline."""
        text = text.strip()

        if not text:
            return ""

        response = self.pipeline.process(text)

        if speak and response:
            self.speak(response)

        return response

    def speak(self, text: str) -> None:
        """Speak text using local TTS."""
        if not text:
            return

        with self._speak_lock:
            self.events.publish(
                EventType.SPEAKING_START,
                text=text,
            )

            try:
                self.tts.speak(text)
            except Exception:
                self.logger.exception("TTS failure")
            finally:
                self.events.publish(
                    EventType.SPEAKING_END,
                )

    def stop_speaking(self) -> None:
        try:
            self.tts.stop()
        except Exception:
            self.logger.exception("Failed to stop TTS")

"""Voice assistant pipeline."""

from __future__ import annotations

import threading

from app.agent.events import EventType, get_event_bus
from app.agent.logging import logger
from app.agent.pipeline import AgentPipeline
from app.agent.router import Router
from app.voice.stt import SpeechToText
from app.voice.tts import TextToSpeech
from app.voice.wakeword import WakeWord


class VoiceAssistant:
    """Connect speech recognition, routing, and speech output."""

    def __init__(self, router: Router | None = None, pipeline: AgentPipeline | None = None, tts: TextToSpeech | None = None):
        self.pipeline = pipeline or AgentPipeline(router=router or Router())
        self.router = self.pipeline.router
        self.stt = SpeechToText(model_size="base")
        self.tts = tts or TextToSpeech()
        self.wakeword = WakeWord("jarvis")
        self.events = get_event_bus()
        self._speaking = False
        self._speak_lock = threading.Lock()

    @property
    def speaking(self) -> bool:
        return self._speaking

    def listen_once(self, audio_or_seconds=5) -> str:
        if isinstance(audio_or_seconds, (int, float)):
            return self.stt.listen(int(audio_or_seconds))
        return self.stt.transcribe(audio_or_seconds)

    def process_text(self, text: str) -> str:
        command = self.wakeword.extract_command(text) or text.strip()
        if not command:
            return ""
        response = self.pipeline.process(command)
        if response:
            self.speak(response)
        return response

    def speak(self, text: str):
        if not text.strip():
            return
        with self._speak_lock:
            self._speaking = True
            self.events.publish(EventType.SPEAKING_START, text=text)
            try:
                self.tts.speak(text)
            except Exception as exc:
                logger.exception("TTS failure")
                self.events.publish(EventType.ERROR, component="tts", error=str(exc))
            finally:
                self._speaking = False
                self.events.publish(EventType.SPEAKING_END)

    def stop_speaking(self):
        stop = getattr(self.tts, "stop", None)
        if stop:
            stop()

    def process_voice(self, seconds: int = 5) -> str:
        text = self.listen_once(seconds)
        if not text:
            return ""
        return self.process_text(text)

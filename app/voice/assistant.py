"""Voice assistant pipeline."""

from __future__ import annotations

from app.agent.router import Router
from app.voice.stt import SpeechToText
from app.voice.tts import TextToSpeech
from app.voice.wakeword import WakeWord


class VoiceAssistant:
    """Connect speech recognition, routing, and speech output."""

    def __init__(self, router: Router | None = None):
        self.router = router if router is not None else Router()
        self.stt = SpeechToText(model_size="base")
        self.tts = TextToSpeech()
        self.wakeword = WakeWord("jarvis")

    def listen_once(self, audio_or_seconds=5) -> str:
        if isinstance(audio_or_seconds, (int, float)):
            return self.stt.listen(int(audio_or_seconds))
        return self.stt.transcribe(audio_or_seconds)

    def process_text(self, text: str) -> str:
        command = self.wakeword.extract_command(text) or text.strip()
        if not command:
            return ""
        response = self.router.route(command)
        if response:
            self.tts.speak(response)
        return response

    def process_voice(self, seconds: int = 5) -> str:
        text = self.listen_once(seconds)
        if not text:
            return ""
        return self.process_text(text)

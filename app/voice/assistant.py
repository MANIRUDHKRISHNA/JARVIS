"""Voice assistant pipeline."""

from __future__ import annotations

from app.agent.router import Router
from app.voice.stt import SpeechToText
from app.voice.tts import TextToSpeech


class VoiceAssistant:
    """Connect speech recognition, routing, and speech output."""

    def __init__(self, router: Router | None = None):
        self.router = router if router is not None else Router()
        self.stt = SpeechToText(model_size="base")
        self.tts = TextToSpeech()

    def listen_once(self, seconds: int = 5) -> str:
        return self.stt.listen(seconds)

    def process_voice(self, seconds: int = 5) -> str:
        text = self.listen_once(seconds)
        if not text:
            return ""
        response = self.router.route(text)
        if response:
            self.tts.speak(response)
        return response

"""Lifecycle-managed background voice engine for JARVIS."""

from __future__ import annotations

import threading
import time

from app.agent.events import EventType, get_event_bus
from app.agent.logging import logger
from app.voice.assistant import VoiceAssistant
from app.voice.microphone import Microphone
from app.voice.stt import SpeechToText
from app.voice.vad import VoiceActivityDetector
from app.voice.wakeword import WakeWord


class BackgroundVoiceEngine:
    """Continuously listen for speech and process wake-word commands."""

    def __init__(self, assistant: VoiceAssistant | None = None, microphone=None, stt=None, vad=None, wakeword=None):
        self.assistant = assistant or VoiceAssistant()
        self.microphone = microphone or Microphone()
        self.stt = stt or self.assistant.stt
        self.vad = vad or VoiceActivityDetector()
        self.wakeword = wakeword or WakeWord("jarvis")
        self.events = get_event_bus()
        self._thread = None
        self._stop_event = threading.Event()
        self._running = False
        self.on_status = None

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> bool:
        if self._running:
            return True
        self._stop_event.clear()
        try:
            self.microphone.start()
        except Exception as exc:
            logger.exception("Could not start microphone")
            self.events.publish(EventType.ERROR, component="microphone", error=str(exc))
            return False
        self._running = True
        self._thread = threading.Thread(target=self._run, name="JARVIS-Voice", daemon=True)
        self._thread.start()
        self.events.publish(EventType.LISTENING_STARTED)
        self._status("Listening")
        return True

    def stop(self):
        if not self._running:
            return
        self._stop_event.set()
        try:
            self.microphone.stop()
        except Exception:
            logger.exception("Microphone stop failed")
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=3)
        self._thread = None
        self._running = False
        self.events.publish(EventType.LISTENING_STOPPED)
        self._status("Stopped")

    def _status(self, message: str):
        if self.on_status:
            try:
                self.on_status(message)
            except Exception:
                pass

    def _run(self):
        while not self._stop_event.is_set():
            try:
                audio = self.microphone.read(timeout=0.5)
                if audio is None or not len(audio):
                    continue
                if not self.vad.is_speech(audio):
                    continue
                self.events.publish(EventType.SPEECH_START)
                chunks = [audio]
                silence_count = 0
                while not self._stop_event.is_set() and silence_count < 5:
                    chunk = self.microphone.read(timeout=0.5)
                    if chunk is None:
                        continue
                    chunks.append(chunk)
                    silence_count = 0 if self.vad.is_speech(chunk) else silence_count + 1
                self.events.publish(EventType.SPEECH_END)
                text = self.stt.transcribe(self.microphone.combine(chunks)).strip()
                if not text or not self.wakeword.detect(text):
                    continue
                self.events.publish(EventType.WAKE_WORD, text=text)
                command = self.wakeword.remove(text).strip()
                if command:
                    self.assistant.process_text(command)
                else:
                    self.assistant.speak("Yes?")
            except Exception as exc:
                logger.exception("Voice worker failure")
                self.events.publish(EventType.ERROR, component="voice", error=str(exc))
                self._status(f"Voice error: {exc}")
                time.sleep(1)


BackgroundVoice = BackgroundVoiceEngine

"""Single lifecycle coordinator for the local JARVIS voice interface."""

from __future__ import annotations

from threading import Event, RLock, Thread, current_thread

from app.agent.events import EventType, get_event_bus
from app.agent.logging import get_logger
from app.voice.assistant import VoiceAssistant
from app.voice.command_capture import CommandCapture
from app.voice.microphone import Microphone
from app.voice.modes import VoiceMode
from app.voice.state_machine import VoiceState, VoiceStateMachine
from app.voice.stt import SpeechToText
from app.voice.vad import VoiceActivityDetector
from app.voice.wake_word_engine import WakeWordEngine


class VoiceRuntime:
    """Owns the one microphone stream and every voice worker.

    The runtime deliberately has no alternate router or brain: transcribed
    commands are sent through :class:`VoiceAssistant`, which uses the shared
    ``AgentPipeline``.
    """

    def __init__(self, assistant: VoiceAssistant, *, microphone: Microphone | None = None,
                 stt: SpeechToText | None = None, vad: VoiceActivityDetector | None = None,
                 wake_engine: WakeWordEngine | None = None, mode: VoiceMode = VoiceMode.DISABLED,
                 capture: CommandCapture | None = None):
        self.assistant = assistant
        self.microphone = microphone or Microphone()
        self.stt = stt or SpeechToText()
        self.vad = vad or VoiceActivityDetector()
        self.wake_engine = wake_engine
        self.mode = VoiceMode(mode)
        self.capture = capture or CommandCapture(self.microphone, self.vad)
        self.machine = VoiceStateMachine()
        self.events, self.logger = get_event_bus(), get_logger()
        self._lock, self._stop = RLock(), Event()
        self._thread: Thread | None = None

    @property
    def state(self) -> VoiceState:
        return self.machine.state

    @property
    def running(self) -> bool:
        return self.state not in {VoiceState.DISABLED, VoiceState.STOPPING, VoiceState.ERROR}

    def _transition(self, target: VoiceState) -> None:
        state = self.machine.transition(target)
        self.events.publish(EventType.VOICE_STATE, state=state.value, mode=self.mode.value)

    def start(self, mode: VoiceMode | None = None) -> None:
        with self._lock:
            if self.running:
                return
            self.mode = VoiceMode(mode or self.mode)
            if self.mode is VoiceMode.DISABLED:
                return
            self._transition(VoiceState.STARTING)
            try:
                self.microphone.start()
                self._stop.clear()
                if self.mode is VoiceMode.WAKE_WORD:
                    if self.wake_engine is None:
                        raise RuntimeError("Wake-word mode needs an acoustic wake-word engine.")
                    self.wake_engine.start()
                    self._thread = Thread(target=self._wake_loop, name="JARVIS-Voice", daemon=True)
                    self._thread.start()
                self._transition(VoiceState.STANDBY)
                self.events.publish(EventType.LISTENING_STARTED)
            except Exception as exc:
                self._transition(VoiceState.ERROR)
                self.microphone.stop()
                raise RuntimeError(f"Voice start failed: {exc}") from exc

    def stop(self) -> None:
        with self._lock:
            if self.state is VoiceState.DISABLED:
                return
            if self.state is not VoiceState.STOPPING:
                self._transition(VoiceState.STOPPING)
            self._stop.set()
            if self.wake_engine:
                self.wake_engine.stop()
            self.assistant.stop_speaking()
            self.microphone.stop()
            thread, self._thread = self._thread, None
        if thread and thread is not current_thread():
            thread.join(timeout=3)
        with self._lock:
            self._transition(VoiceState.DISABLED)
            self.events.publish(EventType.LISTENING_STOPPED)

    def push_to_talk(self) -> None:
        if self.mode is not VoiceMode.PUSH_TO_TALK or self.state is not VoiceState.STANDBY:
            raise RuntimeError("Push-to-talk is unavailable in the current voice state.")
        Thread(target=self._capture_and_process, name="JARVIS-Voice-Command", daemon=True).start()

    def _wake_loop(self) -> None:
        while not self._stop.is_set():
            audio = self.microphone.read(timeout=0.5)
            if audio.size == 0 or self.wake_engine is None:
                continue
            result = self.wake_engine.process_audio(audio)
            if result.detected:
                self.events.publish(EventType.WAKE_WORD, confidence=result.confidence, keyword=result.keyword)
                self._transition(VoiceState.WAKE_DETECTED)
                self._capture_and_process()

    def _capture_and_process(self) -> None:
        try:
            self._transition(VoiceState.LISTENING)
            audio = self.capture.capture(self._stop)
            self._transition(VoiceState.TRANSCRIBING)
            text = self.stt.transcribe(audio).strip()
            if not text:
                self._transition(VoiceState.STANDBY)
                return
            self._transition(VoiceState.PROCESSING)
            response = self.assistant.process_text(text, speak=False)
            if response:
                self._transition(VoiceState.SPEAKING)
                if self.wake_engine:
                    self.wake_engine.pause()
                try:
                    self.assistant.speak(response)
                finally:
                    if self.wake_engine:
                        self.wake_engine.resume()
            if not self._stop.is_set():
                self._transition(VoiceState.STANDBY)
        except InterruptedError:
            if not self._stop.is_set():
                self._transition(VoiceState.STANDBY)
        except Exception as exc:
            self.logger.exception("Voice command failed")
            if not self._stop.is_set():
                self._transition(VoiceState.ERROR)
                self.events.publish(EventType.ERROR, message=f"Voice error: {exc}")
                self._transition(VoiceState.STANDBY)

"""Local acoustic wake-word engine."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
import time


@dataclass(frozen=True)
class WakeWordResult:
    detected: bool
    confidence: float = 0.0
    keyword: str | None = None


class WakeWordEngine:
    """Backend-neutral wake-word engine interface."""

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def pause(self) -> None:
        raise NotImplementedError

    def resume(self) -> None:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError

    @property
    def is_running(self) -> bool:
        raise NotImplementedError

    def process_audio(self, audio) -> WakeWordResult:
        raise NotImplementedError


class OpenWakeWordEngine(WakeWordEngine):
    """Optional local openWakeWord adapter.

    A model path/name must be explicitly configured: this class never claims
    that an arbitrary installed model recognises a particular phrase.
    """

    def __init__(self, model_paths: list[str], threshold: float = 0.5, cooldown: float = 2.0):
        self.model_paths = list(model_paths)
        self.threshold = threshold
        self.cooldown = cooldown
        self._lock = RLock()
        self._model = None
        self._running = False
        self._paused = False
        self._last_detection = 0.0

    def start(self) -> None:
        if not self.model_paths:
            raise RuntimeError("No openWakeWord model paths are configured.")
        try:
            from openwakeword.model import Model
        except ImportError as exc:
            raise RuntimeError("openWakeWord is not installed.") from exc
        with self._lock:
            self._model = Model(wakeword_models=self.model_paths)
            self._running, self._paused = True, False

    def stop(self) -> None:
        with self._lock:
            self._running, self._paused, self._model = False, False, None

    def pause(self) -> None:
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            if self._running:
                self._paused = False

    def reset(self) -> None:
        with self._lock:
            self._last_detection = 0.0

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running and not self._paused

    def process_audio(self, audio) -> WakeWordResult:
        with self._lock:
            if not self._running or self._paused or self._model is None:
                return WakeWordResult(False)
            scores = self._model.predict(audio)
            keyword, confidence = max(scores.items(), key=lambda item: item[1], default=(None, 0.0))
            now = time.monotonic()
            if confidence >= self.threshold and now - self._last_detection >= self.cooldown:
                self._last_detection = now
                return WakeWordResult(True, float(confidence), keyword)
            return WakeWordResult(False, float(confidence), keyword)

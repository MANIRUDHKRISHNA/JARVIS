"""Microphone capture for JARVIS."""

from __future__ import annotations

import queue
from threading import RLock

import numpy as np
import sounddevice as sd


class Microphone:
    """Capture microphone blocks without opening hardware at construction."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1, block_duration: float = 0.25, device=None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_duration = block_duration
        self.block_size = int(sample_rate * block_duration)
        self.queue = queue.Queue(maxsize=20)
        self.stream = None
        self.device = device
        self._lock = RLock()
        self._paused = False

    def _callback(self, indata, frames, time_info, status):
        if status:
            return
        data = indata.copy()
        try:
            self.queue.put_nowait(data)
        except queue.Full:
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(data)
            except queue.Empty:
                pass

    @property
    def running(self) -> bool:
        with self._lock:
            return self.stream is not None and bool(getattr(self.stream, "active", True))

    def start(self):
        """Open the single owned input stream."""
        with self._lock:
            if self.stream is not None:
                if self._paused:
                    self.stream.start()
                    self._paused = False
                return
            self.stream = sd.InputStream(
                device=self.device,
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=self.block_size,
                dtype="float32",
                callback=self._callback,
            )
            self.stream.start()
            self._paused = False

    def stop(self):
        with self._lock:
            stream, self.stream = self.stream, None
            self._paused = False
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

    def pause(self) -> None:
        with self._lock:
            if self.stream is not None and not self._paused:
                self.stream.stop()
                self._paused = True

    def resume(self) -> None:
        self.start()

    def restart(self) -> None:
        self.stop()
        self.start()

    def read(self, timeout: float = 1.0):
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return np.array([], dtype=np.float32)

    @staticmethod
    def combine(chunks: list[np.ndarray]) -> np.ndarray:
        if not chunks:
            return np.empty((0, 1), dtype=np.float32)
        return np.concatenate(chunks, axis=0)

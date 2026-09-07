"""Microphone capture for JARVIS."""

from __future__ import annotations

import queue

import numpy as np
import sounddevice as sd


class Microphone:
    """Capture microphone blocks without opening hardware at construction."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1, block_duration: float = 0.25):
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_duration = block_duration
        self.block_size = int(sample_rate * block_duration)
        self.queue = queue.Queue(maxsize=20)
        self.stream = None

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

    def start(self):
        if self.stream is not None:
            return
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            blocksize=self.block_size,
            dtype="float32",
            callback=self._callback,
        )
        self.stream.start()

    def stop(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

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

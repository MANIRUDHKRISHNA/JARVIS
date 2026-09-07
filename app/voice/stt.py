"""Local speech-to-text using faster-whisper."""

from __future__ import annotations

import tempfile
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


class SpeechToText:
    """Local Whisper speech recognizer."""

    def __init__(self, model_size: str = "base", sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def record(self, seconds: int = 5) -> np.ndarray:
        audio = sd.rec(int(seconds * self.sample_rate), samplerate=self.sample_rate, channels=1, dtype="float32")
        sd.wait()
        return audio.flatten()

    def transcribe_audio(self, audio: np.ndarray) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
            path = Path(temp.name)
        try:
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(self.sample_rate)
                pcm = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
                wav.writeframes(pcm.tobytes())
            segments, _ = self.model.transcribe(str(path), beam_size=5)
            return " ".join(segment.text.strip() for segment in segments).strip()
        finally:
            path.unlink(missing_ok=True)

    def listen(self, seconds: int = 5) -> str:
        return self.transcribe_audio(self.record(seconds))

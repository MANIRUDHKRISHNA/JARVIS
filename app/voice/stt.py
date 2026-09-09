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

    def __init__(self, model_size: str = "base", sample_rate: int = 16000, language: str | None = None, compute_type: str = "float16", device: str = "cuda"):
        self.sample_rate = sample_rate
        self.model_size = model_size
        self.language = language
        self.compute_type = compute_type
        self.device = device
        self.model = None

    def _model(self):
        if self.model is None:
            try:
                self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
            except Exception:
                if self.device != "cpu":
                    self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                else:
                    raise
        return self.model

    def record(self, seconds: int = 5) -> np.ndarray:
        audio = sd.rec(int(seconds * self.sample_rate), samplerate=self.sample_rate, channels=1, dtype="float32")
        sd.wait()
        return audio.flatten()

    def transcribe(self, audio: np.ndarray) -> str:
        audio = np.asarray(audio, dtype=np.float32)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
            path = Path(temp.name)
        try:
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(self.sample_rate)
                pcm = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
                wav.writeframes(pcm.tobytes())
            segments, _ = self._model().transcribe(str(path), beam_size=5, vad_filter=True, language=self.language)
            return " ".join(segment.text.strip() for segment in segments).strip()
        finally:
            path.unlink(missing_ok=True)

    def listen(self, seconds: int = 5) -> str:
        return self.transcribe(self.record(seconds))

    def transcribe_audio(self, audio: np.ndarray) -> str:
        """Backward-compatible alias for transcribe."""

        return self.transcribe(audio)

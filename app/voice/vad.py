"""Simple local voice activity detection."""

from __future__ import annotations

import numpy as np


class VoiceActivityDetector:
    """Energy-based voice activity detector."""

    def __init__(self, threshold: float = 0.015):
        self.threshold = threshold

    def volume(self, audio: np.ndarray) -> float:
        if audio is None or len(audio) == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(audio))))

    def is_speech(self, audio: np.ndarray) -> bool:
        return self.volume(audio) >= self.threshold

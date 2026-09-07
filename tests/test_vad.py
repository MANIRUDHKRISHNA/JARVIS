import numpy as np

from app.voice.vad import VoiceActivityDetector


def test_silence_is_not_speech():
    audio = np.zeros((1600, 1), dtype=np.float32)
    assert VoiceActivityDetector(0.015).is_speech(audio) is False


def test_loud_signal_is_speech():
    audio = np.ones((1600, 1), dtype=np.float32) * 0.1
    assert VoiceActivityDetector(0.015).is_speech(audio) is True

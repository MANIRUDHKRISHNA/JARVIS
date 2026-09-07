import numpy as np

from app.voice.vad import VoiceActivityDetector
from app.voice.wakeword import WakeWord


def test_wake_word_detection():
    wake = WakeWord("jarvis")
    assert wake.matches("Hey Jarvis")
    assert wake.matches("JARVIS open notepad")
    assert not wake.matches("Open notepad")


def test_command_extraction():
    wake = WakeWord("jarvis")
    assert wake.extract_command("Hey Jarvis open Notepad").lower() == "open notepad"


def test_vad_silence():
    assert not VoiceActivityDetector(0.015).is_speech(np.zeros(16000, dtype=np.float32))


def test_vad_speech():
    assert VoiceActivityDetector(0.015).is_speech(np.ones(16000, dtype=np.float32) * 0.1)

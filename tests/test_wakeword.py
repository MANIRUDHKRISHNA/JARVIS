from app.voice.wakeword import WakeWordDetector


def test_wake_word_detection():
    detector = WakeWordDetector(["jarvis"])
    assert detector.detect("Jarvis open Notepad")


def test_wake_word_missing():
    detector = WakeWordDetector(["jarvis"])
    assert not detector.detect("open Notepad")


def test_remove_wake_word():
    detector = WakeWordDetector(["jarvis"])
    assert detector.remove("Jarvis open Notepad") == "open Notepad"

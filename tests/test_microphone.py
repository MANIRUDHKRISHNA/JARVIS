from app.voice.microphone import Microphone


def test_microphone_creation():
    microphone = Microphone()
    assert microphone.sample_rate == 16000
    assert microphone.channels == 1
    microphone.stop()

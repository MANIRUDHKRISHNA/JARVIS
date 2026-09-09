import numpy as np

from app.voice.command_capture import CommandCapture


class FakeMicrophone:
    def __init__(self, frames):
        self.frames = list(frames)

    def read(self, timeout=1.0):
        if not self.frames:
            return np.empty((0, 1), dtype=np.float32)

        return self.frames.pop(0)

    @staticmethod
    def combine(chunks):
        if not chunks:
            return np.empty((0, 1), dtype=np.float32)

        return np.concatenate(chunks, axis=0)


class FakeVAD:
    def __init__(self, speech_frames):
        self.speech_frames = iter(speech_frames)

    def is_speech(self, audio):
        return next(self.speech_frames)


def test_capture_collects_speech():
    speech = np.ones((4000, 1), dtype=np.float32)
    silence = np.zeros((4000, 1), dtype=np.float32)

    microphone = FakeMicrophone([
        speech,
        silence,
        silence,
    ])

    vad = FakeVAD([
        True,
        False,
        False,
    ])

    capture = CommandCapture(
        microphone,
        vad,
        min_speech_duration=0.1,
        silence_timeout=0.0,
        max_command_duration=5.0,
    )

    audio = capture.capture()

    assert audio.shape[0] == 12000
    assert audio.shape[1] == 1
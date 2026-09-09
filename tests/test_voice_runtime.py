from app.voice.modes import VoiceMode
from app.voice.runtime import VoiceRuntime
from app.voice.state_machine import VoiceState


class FakeMicrophone:
    def __init__(self): self.started = self.stopped = False
    def start(self): self.started = True
    def stop(self): self.stopped = True
    def pause(self): pass
    def resume(self): self.started = True
    def read(self, timeout=0.5): return []


class FakeSTT:
    def transcribe(self, audio): return "open calculator"


class FakeVAD: pass


class FakeCapture:
    def capture(self, cancelled): return [1]


class FakeTTS:
    def __init__(self): self.spoken = []; self.stopped = False
    def speak(self, text): self.spoken.append(text)
    def stop(self): self.stopped = True


class FakeAssistant:
    def __init__(self): self.tts = FakeTTS(); self.requests = []
    def process_text(self, text, speak=False): self.requests.append((text, speak)); return "Done"
    def speak(self, text): self.tts.speak(text)
    def stop_speaking(self): self.tts.stop()


def make_runtime(mode=VoiceMode.PUSH_TO_TALK):
    microphone, assistant = FakeMicrophone(), FakeAssistant()
    return VoiceRuntime(assistant, microphone=microphone, stt=FakeSTT(), vad=FakeVAD(), mode=mode, capture=FakeCapture()), microphone, assistant


def test_disabled_mode_does_not_open_microphone():
    runtime, microphone, _ = make_runtime(VoiceMode.DISABLED)
    runtime.start()
    assert runtime.state is VoiceState.DISABLED
    assert not microphone.started


def test_push_to_talk_routes_through_shared_assistant():
    runtime, microphone, assistant = make_runtime()
    runtime.start()
    runtime._capture_and_process()
    assert microphone.started
    assert assistant.requests == [("open calculator", False)]
    assert assistant.tts.spoken == ["Done"]
    assert runtime.state is VoiceState.STANDBY
    runtime.stop()
    assert microphone.stopped


def test_wake_mode_requires_real_acoustic_backend():
    runtime, _, _ = make_runtime(VoiceMode.WAKE_WORD)
    try:
        runtime.start()
    except RuntimeError as exc:
        assert "acoustic wake-word engine" in str(exc)
    else:
        raise AssertionError("wake-word mode must reject a missing backend")


def test_pause_resume_do_not_replace_microphone_owner():
    runtime, microphone, _ = make_runtime()
    runtime.start()
    runtime.pause()
    runtime.resume()
    assert microphone.started

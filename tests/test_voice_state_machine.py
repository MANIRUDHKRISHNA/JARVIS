import pytest

from app.voice.state_machine import VoiceState, VoiceStateMachine


def test_normal_startup_path():
    machine = VoiceStateMachine()

    machine.transition(VoiceState.STARTING)
    machine.transition(VoiceState.STANDBY)

    assert machine.state == VoiceState.STANDBY


def test_normal_wake_path():
    machine = VoiceStateMachine()

    machine.transition(VoiceState.STARTING)
    machine.transition(VoiceState.STANDBY)
    machine.transition(VoiceState.WAKE_DETECTED)
    machine.transition(VoiceState.LISTENING)
    machine.transition(VoiceState.TRANSCRIBING)
    machine.transition(VoiceState.PROCESSING)
    machine.transition(VoiceState.SPEAKING)
    machine.transition(VoiceState.STANDBY)

    assert machine.state == VoiceState.STANDBY


def test_invalid_transition_is_rejected():
    machine = VoiceStateMachine()

    with pytest.raises(ValueError):
        machine.transition(VoiceState.SPEAKING)
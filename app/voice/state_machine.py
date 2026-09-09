"""Voice state machine for JARVIS."""

from __future__ import annotations

from enum import Enum
from threading import RLock


class VoiceState(str, Enum):
    """Runtime states of the voice system."""

    DISABLED = "disabled"
    STARTING = "starting"
    STANDBY = "standby"
    WAKE_DETECTED = "wake_detected"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"
    STOPPING = "stopping"


_ALLOWED_TRANSITIONS: dict[VoiceState, set[VoiceState]] = {
    VoiceState.DISABLED: {
        VoiceState.STARTING,
    },
    VoiceState.STARTING: {
        VoiceState.STANDBY,
        VoiceState.ERROR,
        VoiceState.STOPPING,
    },
    VoiceState.STANDBY: {
        VoiceState.WAKE_DETECTED,
        VoiceState.LISTENING,
        VoiceState.STOPPING,
        VoiceState.ERROR,
    },
    VoiceState.WAKE_DETECTED: {
        VoiceState.LISTENING,
        VoiceState.STANDBY,
        VoiceState.ERROR,
        VoiceState.STOPPING,
    },
    VoiceState.LISTENING: {
        VoiceState.TRANSCRIBING,
        VoiceState.STANDBY,
        VoiceState.ERROR,
        VoiceState.STOPPING,
    },
    VoiceState.TRANSCRIBING: {
        VoiceState.PROCESSING,
        VoiceState.STANDBY,
        VoiceState.ERROR,
        VoiceState.STOPPING,
    },
    VoiceState.PROCESSING: {
        VoiceState.SPEAKING,
        VoiceState.STANDBY,
        VoiceState.ERROR,
        VoiceState.STOPPING,
    },
    VoiceState.SPEAKING: {
        VoiceState.STANDBY,
        VoiceState.LISTENING,
        VoiceState.ERROR,
        VoiceState.STOPPING,
    },
    VoiceState.ERROR: {
        VoiceState.STARTING,
        VoiceState.STANDBY,
        VoiceState.STOPPING,
        VoiceState.DISABLED,
    },
    VoiceState.STOPPING: {
        VoiceState.DISABLED,
    },
}


class VoiceStateMachine:
    """Thread-safe voice state machine."""

    def __init__(self) -> None:
        self._state = VoiceState.DISABLED
        self._lock = RLock()

    @property
    def state(self) -> VoiceState:
        with self._lock:
            return self._state

    def can_transition(self, target: VoiceState) -> bool:
        with self._lock:
            return target in _ALLOWED_TRANSITIONS.get(
                self._state,
                set(),
            )

    def transition(self, target: VoiceState) -> VoiceState:
        with self._lock:
            if target == self._state:
                return self._state

            if target not in _ALLOWED_TRANSITIONS.get(
                self._state,
                set(),
            ):
                raise ValueError(
                    f"Invalid voice state transition: "
                    f"{self._state.value} -> {target.value}"
                )

            self._state = target
            return self._state

    def reset(self) -> None:
        with self._lock:
            self._state = VoiceState.DISABLED
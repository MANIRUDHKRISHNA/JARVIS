"""Voice operating modes for JARVIS."""

from __future__ import annotations

from enum import Enum


class VoiceMode(str, Enum):
    """Supported voice operating modes."""

    DISABLED = "disabled"
    PUSH_TO_TALK = "push_to_talk"
    WAKE_WORD = "wake_word"
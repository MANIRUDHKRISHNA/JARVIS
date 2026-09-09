from app.voice.modes import VoiceMode


def test_voice_modes_exist():
    assert VoiceMode.DISABLED.value == "disabled"
    assert VoiceMode.PUSH_TO_TALK.value == "push_to_talk"
    assert VoiceMode.WAKE_WORD.value == "wake_word"
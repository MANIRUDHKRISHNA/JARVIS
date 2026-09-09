"""Core settings for the JARVIS project."""

APP_NAME = "JARVIS"
APP_VERSION = "0.1.0"
DEFAULT_LANGUAGE = "en"
VOICE_ENABLED = True

# Voice is opt-in at startup so development and tests never claim the
# microphone unexpectedly.  These values are intentionally dependency-free.
VOICE_MODE = "disabled"
VOICE_WAKE_MODEL_PATHS: list[str] = []
VOICE_WAKE_THRESHOLD = 0.5
VOICE_WAKE_COOLDOWN = 2.0
VOICE_MICROPHONE_DEVICE = None
VOICE_VAD_THRESHOLD = 0.015
VOICE_SILENCE_TIMEOUT = 0.8
VOICE_MAX_COMMAND_DURATION = 10.0
VOICE_STT_MODEL = "base"
VOICE_STT_LANGUAGE = None
VOICE_STT_COMPUTE_TYPE = "float16"

"""Voice subsystem for JARVIS."""

from app.voice.assistant import VoiceAssistant
from app.voice.background import BackgroundVoice, BackgroundVoiceEngine
from app.voice.microphone import Microphone
from app.voice.stt import SpeechToText
from app.voice.tts import TextToSpeech
from app.voice.vad import VoiceActivityDetector
from app.voice.wakeword import WakeWord, WakeWordDetector

__all__ = [
	"VoiceAssistant",
	"BackgroundVoice",
	"BackgroundVoiceEngine",
	"Microphone",
	"SpeechToText",
	"TextToSpeech",
	"VoiceActivityDetector",
	"WakeWord",
	"WakeWordDetector",
]

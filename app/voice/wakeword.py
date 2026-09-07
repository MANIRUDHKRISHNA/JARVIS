"""Wake word detection placeholder."""


class WakeWordDetector:
    def detect(self, audio_input: str) -> bool:
        return audio_input.strip().lower() in {"jarvis", "wake"}

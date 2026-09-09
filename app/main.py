"""JARVIS application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.agent.health import run_health_check
from app.agent.logging import get_logger
from app.agent.pipeline import AgentPipeline
from app.ui.main_window import MainWindow
from app.voice.assistant import VoiceAssistant
from app.voice.runtime import VoiceRuntime
from app.voice.modes import VoiceMode


def main() -> int:
    logger = get_logger()

    logger.info("Starting JARVIS.")

    health = run_health_check()

    if not health.get("healthy", False):
        logger.warning(
            "JARVIS health check reported problems: %s",
            health,
        )

    app = QApplication(sys.argv)

    # ONE pipeline.
    pipeline = AgentPipeline()

    # Voice uses the SAME pipeline.
    voice_assistant = VoiceAssistant(
        pipeline=pipeline
    )

    # Voice starts disabled unless a user explicitly enables it in the UI.
    voice_engine = VoiceRuntime(assistant=voice_assistant, mode=VoiceMode.DISABLED)

    window = MainWindow(
        pipeline=pipeline,
        voice_engine=voice_engine,
    )

    window.show()

    try:
        return app.exec()
    finally:
        if voice_engine.running:
            voice_engine.stop()

        logger.info("JARVIS stopped.")


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

"""JARVIS application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.agent.health import ollama_available
from app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS")
    app.setApplicationDisplayName("JARVIS")
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    window.show()

    if not ollama_available():
        window._append(
            "\nWARNING:\n"
            "Ollama is not currently available.\n"
            "Start Ollama before using the local AI brain.\n"
        )

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

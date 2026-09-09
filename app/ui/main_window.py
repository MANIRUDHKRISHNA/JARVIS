"""Main JARVIS desktop window."""

from __future__ import annotations

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.agent.events import EventType, get_event_bus
from app.agent.pipeline import AgentPipeline
from app.voice.assistant import VoiceAssistant
from app.voice.runtime import VoiceRuntime
from app.voice.modes import VoiceMode


class AgentWorker(QThread):
    """Runs the agent pipeline without blocking the GUI."""

    finished = Signal(str)

    def __init__(
        self,
        pipeline: AgentPipeline,
        text: str,
    ):
        super().__init__()

        self.pipeline = pipeline
        self.text = text

    def run(self) -> None:
        response = self.pipeline.process(
            self.text
        )

        self.finished.emit(response)


class MainWindow(QMainWindow):
    """JARVIS desktop interface."""

    def __init__(
        self,
        pipeline: AgentPipeline,
        voice_engine: VoiceRuntime,
    ):
        super().__init__()

        self.pipeline = pipeline
        self.voice_engine = voice_engine

        self.events = get_event_bus()

        self.worker: AgentWorker | None = None

        self.setWindowTitle("JARVIS")
        self.resize(900, 650)

        self._build_ui()

        self.event_timer = QTimer(self)
        self.event_timer.timeout.connect(
            self._process_events
        )
        self.event_timer.start(100)

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        self.status_label = QLabel(
            "JARVIS ready."
        )

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)

        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "Talk to JARVIS..."
        )
        self.input.returnPressed.connect(
            self.send_message
        )

        button_row = QHBoxLayout()

        self.send_button = QPushButton(
            "Send"
        )
        self.send_button.clicked.connect(
            self.send_message
        )

        self.voice_button = QPushButton(
            "Start Voice"
        )
        self.voice_button.clicked.connect(
            self.toggle_voice
        )

        self.stop_button = QPushButton(
            "Stop Speaking"
        )
        self.stop_button.clicked.connect(
            self.stop_speaking
        )

        self.clear_button = QPushButton(
            "Clear Chat"
        )
        self.clear_button.clicked.connect(
            self.clear_chat
        )

        button_row.addWidget(
            self.send_button
        )
        button_row.addWidget(
            self.voice_button
        )
        button_row.addWidget(
            self.stop_button
        )
        button_row.addWidget(
            self.clear_button
        )

        layout.addWidget(
            self.status_label
        )
        layout.addWidget(
            self.chat
        )
        layout.addWidget(
            self.input
        )
        layout.addLayout(
            button_row
        )

        self.setCentralWidget(
            central
        )

    def send_message(self) -> None:
        text = self.input.text().strip()

        if not text:
            return

        if self.pipeline.busy:
            self.status_label.setText(
                "JARVIS is still working..."
            )
            return

        self.input.clear()

        self._append_message(
            "You",
            text,
        )

        self._set_controls_enabled(
            False
        )

        self.status_label.setText(
            "JARVIS is thinking..."
        )

        self.worker = AgentWorker(
            self.pipeline,
            text,
        )

        self.worker.finished.connect(
            self._agent_finished
        )

        self.worker.finished.connect(
            self._worker_finished
        )

        self.worker.start()

    def _agent_finished(
        self,
        response: str,
    ) -> None:
        self._append_message(
            "JARVIS",
            response,
        )

    def _worker_finished(self) -> None:
        self._set_controls_enabled(
            True
        )

        self.status_label.setText(
            "JARVIS ready."
        )

        if self.worker:
            self.worker.deleteLater()

        self.worker = None

    def toggle_voice(self) -> None:
        if self.voice_engine.running:
            self.voice_engine.stop()

            self.voice_button.setText(
                "Start Voice"
            )

            self.status_label.setText(
                "Voice listening stopped."
            )

        else:
            try:
                self.voice_engine.start(VoiceMode.PUSH_TO_TALK)
                # The button click is the explicit activation required for
                # push-to-talk mode; capture itself runs off the GUI thread.
                self.voice_engine.push_to_talk()

                self.voice_button.setText(
                    "Stop Voice"
                )

                self.status_label.setText(
                    "Listening for your command..."
                )

            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "Voice Error",
                    str(exc),
                )

    def stop_speaking(self) -> None:
        self.voice_engine.assistant.stop_speaking()

        self.status_label.setText(
            "Speech stopped."
        )

    def clear_chat(self) -> None:
        self.pipeline.clear_session()
        self.chat.clear()

        self.status_label.setText(
            "Conversation memory cleared."
        )

    def _process_events(self) -> None:
        """Process background events safely on the Qt thread."""
        events = self.events.drain(
            limit=100
        )

        for event in events:
            if event.type == EventType.TOOL_START:
                tool = event.data.get(
                    "tool",
                    "tool",
                )

                self.status_label.setText(
                    f"Using {tool}..."
                )

            elif event.type == EventType.THINKING_START:
                self.status_label.setText(
                    "Thinking..."
                )

            elif event.type == EventType.SPEECH_START:
                self.status_label.setText(
                    "Listening..."
                )

            elif event.type == EventType.SPEAKING_START:
                self.status_label.setText(
                    "Speaking..."
                )

            elif event.type == EventType.LISTENING_STARTED:
                self.status_label.setText(
                    "Listening for wake word..."
                )

            elif event.type == EventType.LISTENING_STOPPED:
                self.status_label.setText(
                    "Voice listening stopped."
                )

            elif event.type == EventType.VOICE_STATE:
                state = event.data.get("state", "unknown").replace("_", " ")
                self.status_label.setText(f"Voice: {state}.")

            elif event.type == EventType.ERROR:
                message = event.data.get(
                    "message",
                    "Unknown error",
                )

                self.status_label.setText(
                    "Error."
                )

                self._append_message(
                    "System",
                    message,
                )

    def _append_message(
        self,
        speaker: str,
        text: str,
    ) -> None:
        self.chat.append(
            f"<b>{speaker}:</b> {text}"
        )

        cursor = self.chat.textCursor()
        cursor.movePosition(
            QTextCursor.End
        )

        self.chat.setTextCursor(
            cursor
        )

    def _set_controls_enabled(
        self,
        enabled: bool,
    ) -> None:
        self.send_button.setEnabled(
            enabled
        )
        self.input.setEnabled(
            enabled
        )

    def closeEvent(self, event) -> None:
        if self.voice_engine.running:
            self.voice_engine.stop()

        if (
            self.worker
            and self.worker.isRunning()
        ):
            self.worker.wait(
                3000
            )

        event.accept()

"""Standalone JARVIS desktop interface."""

from __future__ import annotations

from PySide6.QtCore import QThread, Qt, Signal, Slot
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

from app.agent.router import Router
from app.agent.session import Session
from app.config.app_config import AppConfig
from app.ui.hotkey import GlobalHotkey
from app.ui.tray import JarvisTray
from app.voice.assistant import VoiceAssistant


class RequestWorker(QThread):
    """Run one Router request away from the GUI thread."""

    finished = Signal(str)
    failed = Signal(str)
    confirmation_requested = Signal(object)

    def __init__(self, text: str, config: AppConfig, session: Session):
        super().__init__()
        self.text = text
        self.config = config
        self.session = session

    def run(self):
        try:
            router = Router(
                model=self.config.get("model", "qwen3:8b"),
                confirm_callback=self.request_confirmation,
                session=self.session,
            )
            self.finished.emit(router.route(self.text))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def request_confirmation(self, message: str) -> bool:
        request = type("Confirmation", (), {})()
        request.message = message
        request.approved = False
        request.event = __import__("threading").Event()
        self.confirmation_requested.emit(request)
        request.event.wait()
        return request.approved


class MainWindow(QMainWindow):
    """Main JARVIS application window."""

    def __init__(self):
        super().__init__()
        self.config = AppConfig()
        self.allow_close = False
        self.session = Session()
        self.worker = None
        self.voice_assistant = None
        self._build_ui()

        self.tray = JarvisTray(self)
        self.tray.show()
        self.hotkey = GlobalHotkey(self.show_from_hotkey)
        self.hotkey.start()

        self.resize(
            self.config.get("window_width", 1100),
            self.config.get("window_height", 750),
        )
        self._append("JARVIS: Online.\nLocal brain: Qwen3 8B\n")

        if self.config.get("start_minimized", False):
            self.hide()

    def _build_ui(self):
        self.setWindowTitle("JARVIS")
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        title = QLabel("JARVIS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 32px; font-weight: bold; padding: 12px;")
        layout.addWidget(title)

        self.status = QLabel("ONLINE")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask JARVIS...")
        self.input.returnPressed.connect(self.submit)
        row.addWidget(self.input)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.submit)
        row.addWidget(self.send_button)

        self.voice_button = QPushButton("Voice")
        self.voice_button.clicked.connect(self.voice_request)
        row.addWidget(self.voice_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_chat)
        row.addWidget(self.clear_button)
        layout.addLayout(row)

    def _append(self, text: str):
        self.output.append(text)

    @Slot()
    def submit(self):
        text = self.input.text().strip()
        if not text or self.worker is not None:
            return
        self.input.clear()
        self._append(f"\nYou:\n{text}\n")
        self._set_busy(True)
        self.worker = RequestWorker(text, self.config, self.session)
        self.worker.finished.connect(self._request_finished)
        self.worker.failed.connect(self._request_failed)
        self.worker.confirmation_requested.connect(self._confirm_request)
        self.worker.finished.connect(self._clear_worker)
        self.worker.failed.connect(self._clear_worker)
        self.worker.start()

    @Slot(str)
    def _request_finished(self, result: str):
        self._append(f"JARVIS:\n{result}\n")

    @Slot(str)
    def _request_failed(self, error: str):
        self._append(f"JARVIS ERROR:\n{error}\n")

    def _clear_worker(self, _value):
        self._set_busy(False)
        self.worker = None

    @Slot(object)
    def _confirm_request(self, request):
        result = QMessageBox.question(
            self,
            "JARVIS Confirmation",
            request.message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        request.approved = result == QMessageBox.StandardButton.Yes
        request.event.set()

    @Slot()
    def voice_request(self):
        self._set_busy(True)
        self._append("\nListening...\n")
        try:
            if self.voice_assistant is None:
                self.voice_assistant = VoiceAssistant(router=Router(session=self.session))
            text = self.voice_assistant.listen_once(self.config.get("voice_record_seconds", 5))
            if not text:
                self._append("JARVIS: I did not hear anything.\n")
                return
            self._append(f"You:\n{text}\n")
            response = self.voice_assistant.router.route(text)
            self._append(f"JARVIS:\n{response}\n")
            self.voice_assistant.tts.speak(response)
        except Exception as exc:
            self._append(f"VOICE ERROR:\n{type(exc).__name__}: {exc}\n")
        finally:
            self._set_busy(False)

    def clear_chat(self):
        self.session.clear()
        self.output.clear()
        self._append("JARVIS: Conversation cleared.")

    def confirm_action(self, message: str) -> bool:
        result = QMessageBox.question(self, "JARVIS Confirmation", message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        return result == QMessageBox.StandardButton.Yes

    def _set_busy(self, busy: bool):
        self.send_button.setEnabled(not busy)
        self.voice_button.setEnabled(not busy)
        self.input.setEnabled(not busy)
        self.status.setText("THINKING..." if busy else "ONLINE")

    def show_from_hotkey(self):
        self.show()
        self.showNormal()
        self.activateWindow()
        self.raise_()
        self.input.setFocus()

    def closeEvent(self, event):
        if self.config.get("minimize_to_tray", True) and not self.allow_close:
            event.ignore()
            self.hide()
            self.tray.tray.showMessage("JARVIS", "Still running in the system tray.", 2000)
            return
        self.hotkey.stop()
        self.tray.hide()
        self.config.set("window_width", self.width())
        self.config.set("window_height", self.height())
        self.config.save()
        event.accept()

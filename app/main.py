"""JARVIS desktop application."""

import sys
import threading

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QLineEdit,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.agent.router import Router
from app.agent.session import Session
from app.voice.assistant import VoiceAssistant


class ConfirmationRequest:
    """Thread-safe confirmation request."""

    def __init__(self, message: str):
        self.message = message
        self.approved = False
        self.event = threading.Event()

    def wait(self) -> bool:
        """Wait for the GUI response."""

        self.event.wait()

        return self.approved

    def resolve(self, approved: bool):
        """Provide the GUI response."""

        self.approved = approved
        self.event.set()


class BrainWorker(QThread):
    """Run JARVIS processing outside the GUI thread."""

    finished = Signal(str)
    error = Signal(str)
    confirmation_requested = Signal(object)

    def __init__(
        self,
        prompt: str,
        model: str = "qwen3:8b",
        session=None,
    ):
        super().__init__()

        self.prompt = prompt
        self.model = model
        self.session = session

    def run(self):
        """Execute the JARVIS request."""

        try:
            router = Router(
                model=self.model,
                confirm_callback=self.request_confirmation,
                session=self.session,
            )

            response = router.handle(
                self.prompt
            )

            self.finished.emit(response)

        except Exception as exc:
            self.error.emit(str(exc))

    def request_confirmation(
        self,
        message: str,
    ) -> bool:
        """Ask the GUI for permission."""

        request = ConfirmationRequest(
            message
        )

        self.confirmation_requested.emit(
            request
        )

        return request.wait()


class JarvisWindow(QMainWindow):
    """Main JARVIS window."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("JARVIS")
        self.resize(900, 650)

        self.worker = None
        self.session = Session()
        self.voice_assistant = None

        self.setup_ui()

    def setup_ui(self):
        """Create the user interface."""

        central = QWidget()
        layout = QVBoxLayout()

        title = QLabel("JARVIS")
        title.setAlignment(Qt.AlignCenter)

        title.setStyleSheet(
            "font-size: 28px; "
            "font-weight: bold;"
        )

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)

        self.status = QLabel("Ready")
        self.status.setAlignment(Qt.AlignCenter)

        self.input = QLineEdit()

        self.input.setPlaceholderText(
            "Talk to JARVIS..."
        )

        self.input.returnPressed.connect(
            self.send_message
        )

        self.send_button = QPushButton(
            "Send"
        )

        self.send_button.clicked.connect(
            self.send_message
        )

        self.voice_button = QPushButton("Voice")
        self.voice_button.clicked.connect(self.voice_request)

        layout.addWidget(title)
        layout.addWidget(self.chat)
        layout.addWidget(self.status)
        layout.addWidget(self.input)
        layout.addWidget(self.send_button)
        layout.addWidget(self.voice_button)

        central.setLayout(layout)

        self.setCentralWidget(
            central
        )

    def send_message(self):
        """Send a user request."""

        user_text = self.input.text().strip()

        if not user_text:
            return

        self.input.clear()

        self.chat.append(
            f"<b>You:</b> {user_text}"
        )

        self.input.setEnabled(False)
        self.send_button.setEnabled(False)

        self.status.setText(
            "JARVIS is working..."
        )

        self.worker = BrainWorker(
            prompt=user_text,
            model="qwen3:8b",
            session=self.session,
        )

        self.worker.finished.connect(
            self.handle_response
        )

        self.worker.error.connect(
            self.handle_error
        )

        self.worker.confirmation_requested.connect(
            self.handle_confirmation
        )

        self.worker.start()

    def voice_request(self):
        """Capture one push-to-talk request and route it through JARVIS."""

        self.voice_button.setEnabled(False)
        self.status.setText("Listening...")

        try:
            if self.voice_assistant is None:
                self.voice_assistant = VoiceAssistant(
                    router=Router(session=self.session)
                )

            text = self.voice_assistant.listen_once(5)

            if not text:
                self.chat.append("<b>JARVIS:</b> I did not hear anything.")
                return

            self.chat.append(f"<b>You:</b> {text}")
            response = self.voice_assistant.router.route(text)
            self.chat.append(f"<b>JARVIS:</b> {response}")
            self.voice_assistant.tts.speak(response)

        except Exception as exc:
            self.chat.append(f"<b>Voice error:</b> {exc}")

        finally:
            self.voice_button.setEnabled(True)
            self.status.setText("Ready")

    def handle_confirmation(
        self,
        request,
    ):
        """Display a permission dialog."""

        dialog = QMessageBox(self)

        dialog.setWindowTitle(
            "JARVIS Permission Request"
        )

        dialog.setIcon(
            QMessageBox.Warning
        )

        dialog.setText(
            "JARVIS wants to perform an action."
        )

        dialog.setInformativeText(
            request.message
        )

        dialog.setStandardButtons(
            QMessageBox.Yes
            | QMessageBox.No
        )

        dialog.setDefaultButton(
            QMessageBox.No
        )

        result = dialog.exec()

        request.resolve(
            result == QMessageBox.Yes
        )

    def handle_response(
        self,
        response: str,
    ):
        """Display JARVIS's response."""

        self.chat.append(
            f"<b>JARVIS:</b> {response}"
        )

        self.status.setText(
            "Ready"
        )

        self.input.setEnabled(True)
        self.send_button.setEnabled(True)

        self.input.setFocus()

        self.worker = None

    def handle_error(
        self,
        error: str,
    ):
        """Display an error."""

        self.chat.append(
            f"<b>Error:</b> {error}"
        )

        self.status.setText(
            "Error"
        )

        self.input.setEnabled(True)
        self.send_button.setEnabled(True)

        self.input.setFocus()

        self.worker = None


def main():
    """Start JARVIS."""

    app = QApplication(sys.argv)

    window = JarvisWindow()
    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()
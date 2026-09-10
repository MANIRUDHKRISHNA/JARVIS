"""Main JARVIS desktop window."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QThread, QTimer, Signal, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.agent.events import EventType, get_event_bus
from app.agent.pipeline import AgentPipeline
from app.voice.runtime import VoiceRuntime
from app.voice.modes import VoiceMode


class AgentWorker(QThread):
    """Runs the agent pipeline without blocking the GUI."""

    finished = Signal(str)

    def __init__(self, pipeline: AgentPipeline, text: str):
        super().__init__()
        self.pipeline = pipeline
        self.text = text

    def run(self) -> None:
        response = self.pipeline.process(self.text)
        self.finished.emit(response)


class MainWindow(QMainWindow):
    """JARVIS desktop interface."""

    def __init__(self, pipeline: AgentPipeline, voice_engine: VoiceRuntime):
        super().__init__()

        self.pipeline = pipeline
        self.voice_engine = voice_engine
        self.events = get_event_bus()
        self.worker: AgentWorker | None = None
        self._last_activity_message = None
        self._pulse_on = False

        self.setWindowTitle("JARVIS")
        self.resize(1240, 760)
        self.setMinimumSize(980, 620)

        self._build_ui()
        self._apply_theme()

        self.event_timer = QTimer(self)
        self.event_timer.timeout.connect(self._process_events)
        self.event_timer.start(100)

        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._pulse_activity)
        self.pulse_timer.start(500)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("root")
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # Header
        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 12, 18, 12)

        brand = QLabel("JARVIS")
        brand.setObjectName("brand")
        subtitle = QLabel("LOCAL INTELLIGENCE INTERFACE")
        subtitle.setObjectName("subtitle")

        brand_box = QVBoxLayout()
        brand_box.setSpacing(0)
        brand_box.addWidget(brand)
        brand_box.addWidget(subtitle)

        self.connection_dot = QLabel("●")
        self.connection_dot.setObjectName("onlineDot")
        self.connection_state = QLabel("ONLINE")
        self.connection_state.setObjectName("onlineText")

        header_layout.addLayout(brand_box)
        header_layout.addStretch()
        header_layout.addWidget(self.connection_dot)
        header_layout.addWidget(self.connection_state)

        root.addWidget(header)

        # Main body
        body = QHBoxLayout()
        body.setSpacing(12)

        # Left sidebar
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(245)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(14, 14, 14, 14)
        side_layout.setSpacing(10)

        system_title = QLabel("SYSTEM STATUS")
        system_title.setObjectName("sectionTitle")
        side_layout.addWidget(system_title)

        self.task_value = self._status_value("READY")
        self.voice_value = self._status_value("DISABLED")
        self.tools_value = self._status_value("READY")
        self.security_value = self._status_value("CONFIRM")

        side_layout.addWidget(self._status_card("TASK", self.task_value))
        side_layout.addWidget(self._status_card("VOICE", self.voice_value))
        side_layout.addWidget(self._status_card("TOOLS", self.tools_value))
        side_layout.addWidget(self._status_card("SECURITY", self.security_value))

        side_layout.addSpacing(8)

        actions_title = QLabel("QUICK ACTIONS")
        actions_title.setObjectName("sectionTitle")
        side_layout.addWidget(actions_title)

        self.voice_button = QPushButton("◉  Start Voice")
        self.voice_button.setObjectName("secondaryButton")
        self.voice_button.clicked.connect(self.toggle_voice)

        self.stop_button = QPushButton("■  Stop Speaking")
        self.stop_button.setObjectName("secondaryButton")
        self.stop_button.clicked.connect(self.stop_speaking)

        self.clear_button = QPushButton("⌫  Clear Chat")
        self.clear_button.setObjectName("secondaryButton")
        self.clear_button.clicked.connect(self.clear_chat)

        side_layout.addWidget(self.voice_button)
        side_layout.addWidget(self.stop_button)
        side_layout.addWidget(self.clear_button)
        side_layout.addStretch()

        hint = QLabel("JARVIS CORE\nLocal-first • Private • Ready")
        hint.setObjectName("sidebarHint")
        hint.setWordWrap(True)
        side_layout.addWidget(hint)

        body.addWidget(sidebar)

        # Center chat
        center = QFrame()
        center.setObjectName("center")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(10)

        chat_header = QFrame()
        chat_header.setObjectName("chatHeader")
        chat_header_layout = QHBoxLayout(chat_header)
        chat_header_layout.setContentsMargins(14, 10, 14, 10)

        chat_title = QLabel("CONVERSATION")
        chat_title.setObjectName("sectionTitle")
        self.activity_label = QLabel("Ready")
        self.activity_label.setObjectName("activityLabel")

        chat_header_layout.addWidget(chat_title)
        chat_header_layout.addStretch()
        chat_header_layout.addWidget(self.activity_label)

        center_layout.addWidget(chat_header)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setObjectName("chatScroll")
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.chat_container = QWidget()
        self.chat_container.setObjectName("chatContainer")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(16, 14, 16, 14)
        self.chat_layout.setSpacing(4)
        self.chat_layout.addStretch(1)

        self.chat_scroll.setWidget(self.chat_container)
        center_layout.addWidget(self.chat_scroll, 1)

        # Input row
        input_frame = QFrame()
        input_frame.setObjectName("inputFrame")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(8, 8, 8, 8)
        input_layout.setSpacing(8)

        self.input = QLineEdit()
        self.input.setObjectName("input")
        self.input.setPlaceholderText("Ask JARVIS anything...")
        self.input.returnPressed.connect(self.send_message)

        self.send_button = QPushButton("➤")
        self.send_button.setObjectName("sendButton")
        self.send_button.setToolTip("Send message")
        self.send_button.setFixedSize(46, 46)
        self.send_button.clicked.connect(self.send_message)

        input_layout.addWidget(self.input, 1)
        input_layout.addWidget(self.send_button)

        center_layout.addWidget(input_frame)
        body.addWidget(center, 1)

        # Right activity panel
        activity = QFrame()
        activity.setObjectName("activity")
        activity.setFixedWidth(255)
        activity_layout = QVBoxLayout(activity)
        activity_layout.setContentsMargins(14, 14, 14, 14)
        activity_layout.setSpacing(10)

        activity_title = QLabel("ACTIVITY")
        activity_title.setObjectName("sectionTitle")
        activity_layout.addWidget(activity_title)

        state_row = QHBoxLayout()
        state_row.setSpacing(7)

        self.activity_dot = QLabel("●")
        self.activity_dot.setObjectName("activityDot")

        self.activity_state = QLabel("IDLE")
        self.activity_state.setObjectName("activityState")

        state_row.addWidget(self.activity_dot)
        state_row.addWidget(self.activity_state)
        state_row.addStretch(1)

        activity_layout.addLayout(state_row)

        self.activity_detail = QLabel("Waiting for your next command.")
        self.activity_detail.setObjectName("activityDetail")
        self.activity_detail.setWordWrap(True)
        activity_layout.addWidget(self.activity_detail)

        activity_layout.addSpacing(8)

        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setObjectName("activityLog")
        activity_layout.addWidget(self.activity_log, 1)

        model_card = QFrame()
        model_card.setObjectName("modelCard")
        model_layout = QVBoxLayout(model_card)
        model_layout.setContentsMargins(12, 10, 12, 10)

        model_caption = QLabel("CORE")
        model_caption.setObjectName("cardCaption")
        model_name = QLabel("JARVIS / LOCAL")
        model_name.setObjectName("modelName")

        model_layout.addWidget(model_caption)
        model_layout.addWidget(model_name)
        activity_layout.addWidget(model_card)

        body.addWidget(activity)

        root.addLayout(body, 1)
        self.setCentralWidget(central)

        self._append_system("JARVIS initialized. Local core is ready.")
        self._log_activity("System online")

    def _status_value(self, value: str) -> QLabel:
        label = QLabel(value)
        label.setObjectName("statusValue")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return label

    def _status_card(self, title: str, value: QLabel) -> QFrame:
        card = QFrame()
        card.setObjectName("statusCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(11, 9, 11, 9)

        caption = QLabel(title)
        caption.setObjectName("cardCaption")

        layout.addWidget(caption)
        layout.addStretch()
        layout.addWidget(value)

        return card

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QWidget#root {
                background: #070b10;
                color: #d7e4eb;
                font-family: "Segoe UI";
                font-size: 13px;
            }

            QFrame#header,
            QFrame#sidebar,
            QFrame#center,
            QFrame#activity {
                background: #0b1118;
                border: 1px solid #172630;
                border-radius: 14px;
            }

            QFrame#header {
                border-bottom: 1px solid #1c5663;
            }

            QLabel#brand {
                color: #dffcff;
                font-size: 25px;
                font-weight: 700;
                letter-spacing: 3px;
            }

            QLabel#subtitle {
                color: #55717c;
                font-size: 9px;
                letter-spacing: 2px;
            }

            QLabel#onlineDot {
                color: #45d7d2;
                font-size: 13px;
            }

            QLabel#onlineText {
                color: #72cbd0;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 1px;
            }

            QLabel#sectionTitle {
                color: #5e8791;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.6px;
            }

            QFrame#statusCard,
            QFrame#modelCard {
                background: #0e171f;
                border: 1px solid #172c36;
                border-radius: 9px;
            }

            QLabel#cardCaption {
                color: #6d8790;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 1px;
            }

            QLabel#statusValue {
                color: #8ee7e4;
                font-size: 10px;
                font-weight: 700;
            }

            QLabel#sidebarHint {
                color: #425861;
                font-size: 10px;
                line-height: 1.4;
            }

            QPushButton#secondaryButton {
                background: #0e171f;
                color: #a8c3ca;
                border: 1px solid #1a3540;
                border-radius: 8px;
                padding: 10px 12px;
                text-align: left;
            }

            QPushButton#secondaryButton:hover {
                background: #12232b;
                border-color: #27606a;
                color: #d9ffff;
            }

            QPushButton#secondaryButton:pressed {
                background: #0a151b;
            }

            QPushButton#secondaryButton:disabled {
                color: #3f5158;
                border-color: #17252b;
            }

            QFrame#chatHeader {
                background: transparent;
                border-bottom: 1px solid #15252d;
            }

            QScrollArea#chatScroll {
                background: #080e14;
                border: 1px solid #14242c;
                border-radius: 12px;
            }

            QWidget#chatContainer {
                background: #080e14;
            }

            QFrame#userBubble {
                background: #102b34;
                border: 1px solid #23606a;
                border-radius: 12px;
            }

            QFrame#jarvisBubble {
                background: #0d171e;
                border: 1px solid #1b3741;
                border-radius: 12px;
            }

            QLabel#userName {
                color: #6fe1df;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 1px;
            }

            QLabel#jarvisName {
                color: #91eeea;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 1px;
            }

            QLabel#userText,
            QLabel#jarvisText {
                font-size: 13px;
            }

            QLabel#userText {
                color: #d9eef0;
            }

            QLabel#jarvisText {
                color: #c9dce1;
            }

            QFrame#systemMessage {
                background: transparent;
                border-left: 2px solid #24434b;
                border-radius: 2px;
            }

            QLabel#systemTitle {
                color: #557984;
                font-size: 8px;
                font-weight: 700;
                letter-spacing: 1.5px;
            }

            QLabel#systemText {
                color: #607e87;
                font-size: 10px;
            }

            QFrame#inputFrame {
                background: #0c151c;
                border: 1px solid #1b3b45;
                border-radius: 12px;
            }

            QLineEdit#input {
                background: transparent;
                color: #e2f4f5;
                border: none;
                padding: 8px 10px;
                font-size: 13px;
            }

            QLineEdit#input:focus {
                border: none;
            }

            QPushButton#sendButton {
                background: #153a43;
                color: #9af4ef;
                border: 1px solid #276875;
                border-radius: 9px;
                font-size: 18px;
                font-weight: 700;
            }

            QPushButton#sendButton:hover {
                background: #1a4c57;
            }

            QPushButton#sendButton:pressed {
                background: #102e35;
            }

            QLabel#activityLabel {
                color: #66c6c8;
                font-size: 10px;
            }

            QLabel#activityDot {
                color: #45d7d2;
                font-size: 11px;
            }

            QLabel#activityDot[state="ERROR"] {
                color: #d77b7b;
            }

            QLabel#activityDot[state="IDLE"] {
                color: #4f8c91;
            }

            QLabel#activityState {
                color: #d9ffff;
                font-size: 21px;
                font-weight: 700;
                letter-spacing: 1.5px;
            }

            QLabel#activityDetail {
                color: #708891;
                font-size: 11px;
                padding-bottom: 8px;
            }

            QTextEdit#activityLog {
                background: #080e14;
                border: 1px solid #14242c;
                border-radius: 9px;
                padding: 8px;
                color: #79a9b2;
                font-size: 10px;
            }

            QLabel#modelName {
                color: #b8e8eb;
                font-size: 11px;
                font-weight: 600;
            }

            QScrollBar:vertical {
                background: #080e14;
                width: 8px;
                margin: 3px;
            }

            QScrollBar::handle:vertical {
                background: #203943;
                border-radius: 4px;
                min-height: 30px;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """
        )

    # ------------------------------------------------------------------
    # Agent interaction
    # ------------------------------------------------------------------

    def send_message(self) -> None:
        text = self.input.text().strip()

        if not text:
            return

        if self.pipeline.busy:
            self._set_activity("BUSY", "JARVIS is still processing the previous command.")
            return

        self.input.clear()
        self._append_message("You", text, "user")
        self._set_controls_enabled(False)
        self._set_activity("THINKING", "Processing your request...")

        self.worker = AgentWorker(self.pipeline, text)
        self.worker.finished.connect(self._agent_finished)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _agent_finished(self, response: str) -> None:
        self._append_message("JARVIS", response, "assistant")

    def _worker_finished(self) -> None:
        self._set_controls_enabled(True)
        self._set_activity("IDLE", "Waiting for your next command.")

        if self.worker:
            self.worker.deleteLater()

        self.worker = None

    # ------------------------------------------------------------------
    # Voice
    # ------------------------------------------------------------------

    def toggle_voice(self) -> None:
        if self.voice_engine.running:
            self.voice_engine.stop()
            self.voice_button.setText("◉  Start Voice")
            self._set_activity("IDLE", "Voice listening stopped.")
        else:
            try:
                self.voice_engine.start(VoiceMode.PUSH_TO_TALK)
                self.voice_engine.push_to_talk()
                self.voice_button.setText("◉  Stop Voice")
                self._set_activity("LISTENING", "Listening for your command...")
            except Exception as exc:
                QMessageBox.critical(self, "Voice Error", str(exc))
                self._set_activity("ERROR", "Voice system could not be started.")

    def stop_speaking(self) -> None:
        self.voice_engine.assistant.stop_speaking()
        self._set_activity("IDLE", "Speech stopped.")

    def clear_chat(self) -> None:
        self.pipeline.clear_session()

        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._append_system("Conversation cleared.")
        self._set_activity("IDLE", "Conversation cleared.")

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _process_events(self) -> None:
        """Process background events safely on the Qt thread."""
        events = self.events.drain(limit=100)

        for event in events:
            self._refresh_control_center()

            if event.type == EventType.TOOL_START:
                tool = event.data.get("tool", "tool")
                self._set_activity("EXECUTING", f"Using {tool}...")
                self._log_activity(f"Tool started: {tool}")

            elif event.type == EventType.THINKING_START:
                self._set_activity("THINKING", "JARVIS is reasoning...")
                self._log_activity("Thinking started")

            elif event.type == EventType.SPEECH_START:
                self._set_activity("LISTENING", "Voice input detected.")
                self._log_activity("Speech input detected")

            elif event.type == EventType.SPEAKING_START:
                self._set_activity("SPEAKING", "JARVIS is speaking.")
                self._log_activity("Speech output started")

            elif event.type == EventType.LISTENING_STARTED:
                self._set_activity("LISTENING", "Listening for wake word.")
                self._log_activity("Voice listener started.")

            elif event.type == EventType.LISTENING_STOPPED:
                self._set_activity("IDLE", "Voice listening stopped.")
                self._log_activity("Voice listener stopped.")

            elif event.type == EventType.VOICE_STATE:
                state = event.data.get("state", "unknown").replace("_", " ")
                self._set_activity("LISTENING", f"Voice: {state}.")

            elif event.type == EventType.ERROR:
                message = event.data.get("message", "Unknown error")
                self._set_activity("ERROR", message)
                self._append_system(message)
                self._log_activity(f"Error: {message}")

    def _refresh_control_center(self) -> None:
        """Cheap GUI-thread snapshot; expensive work stays in AgentWorker."""
        task = (
            self.pipeline.current_task.diagnostic()
            if self.pipeline.current_task
            else {
                "state": "idle",
                "current_step": None,
                "elapsed_seconds": 0,
            }
        )

        voice = "RUNNING" if self.voice_engine.running else "DISABLED"

        if self.pipeline.busy:
            task_state = str(task["state"]).upper()
        else:
            task_state = "READY"

        self.task_value.setText(task_state)
        self.voice_value.setText(voice)

        # These are presentation labels only. Existing backend behavior is
        # unchanged and no new backend state is introduced.
        self.tools_value.setText("READY")
        self.security_value.setText("CONFIRM")

    # ------------------------------------------------------------------
    # Presentation helpers
    # ------------------------------------------------------------------

    def _set_activity(self, state: str, detail: str) -> None:
        self.activity_state.setText(state)
        self.activity_detail.setText(detail)
        self.activity_label.setText(detail)
        self.activity_dot.setProperty("state", state)
        self.activity_dot.style().unpolish(self.activity_dot)
        self.activity_dot.style().polish(self.activity_dot)

        if state == "ERROR":
            self.connection_state.setText("ATTENTION")
        elif state in {"THINKING", "EXECUTING", "LISTENING", "SPEAKING"}:
            self.connection_state.setText("ACTIVE")
        else:
            self.connection_state.setText("ONLINE")

    def _pulse_activity(self) -> None:
        if self.activity_state.text() in {"THINKING", "EXECUTING", "LISTENING", "SPEAKING"}:
            self._pulse_on = not self._pulse_on
            self.activity_dot.setText("●" if self._pulse_on else "○")
        else:
            self.activity_dot.setText("●")

    def _log_activity(self, message: str) -> None:
        if message == self._last_activity_message:
            return

        self._last_activity_message = message
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.activity_log.append(
            f'<span style="color:#3f626b;">{timestamp}</span>  {message}'
        )
        cursor = self.activity_log.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.activity_log.setTextCursor(cursor)
        self._scroll_activity_to_bottom()

    def _scroll_activity_to_bottom(self) -> None:
        QTimer.singleShot(
            0,
            lambda: self.activity_log.verticalScrollBar().setValue(
                self.activity_log.verticalScrollBar().maximum()
            ),
        )

    def _append_system(self, text: str) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 8, 4, 8)

        card = QFrame()
        card.setObjectName("systemMessage")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 9, 12, 9)
        card_layout.setSpacing(3)

        title = QLabel("SYSTEM")
        title.setObjectName("systemTitle")

        message = QLabel(text)
        message.setObjectName("systemText")
        message.setWordWrap(True)
        message.setTextInteractionFlags(Qt.TextSelectableByMouse)

        card_layout.addWidget(title)
        card_layout.addWidget(message)

        row_layout.addWidget(card)
        row_layout.addStretch(1)

        self.chat_layout.insertWidget(self.chat_layout.count() - 1, row)
        self._scroll_chat_to_bottom()

    def _append_message(self, speaker: str, text: str, kind: str) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 4, 4, 4)

        bubble = QFrame()
        bubble.setObjectName("userBubble" if kind == "user" else "jarvisBubble")
        bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(14, 10, 14, 10)
        bubble_layout.setSpacing(4)

        name = QLabel("YOU" if kind == "user" else "JARVIS")
        name.setObjectName("userName" if kind == "user" else "jarvisName")

        message = QLabel(text)
        message.setObjectName("userText" if kind == "user" else "jarvisText")
        message.setWordWrap(True)
        message.setTextInteractionFlags(Qt.TextSelectableByMouse)
        message.setMaximumWidth(620)

        bubble_layout.addWidget(name)
        bubble_layout.addWidget(message)

        if kind == "user":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0, Qt.AlignRight)
        else:
            row_layout.addWidget(bubble, 0, Qt.AlignLeft)
            row_layout.addStretch(1)

        self.chat_layout.insertWidget(self.chat_layout.count() - 1, row)
        self._scroll_chat_to_bottom()

    def _scroll_chat_to_bottom(self) -> None:
        QTimer.singleShot(
            0,
            lambda: self.chat_scroll.verticalScrollBar().setValue(
                self.chat_scroll.verticalScrollBar().maximum()
            ),
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)

        # Keep message bubbles readable as the window changes size.
        max_width = max(300, min(620, int(self.chat_scroll.viewport().width() * 0.72)))

        for bubble in self.chat_container.findChildren(QFrame):
            if bubble.objectName() in {"userBubble", "jarvisBubble"}:
                for label in bubble.findChildren(QLabel):
                    if label.objectName() in {"userText", "jarvisText"}:
                        label.setMaximumWidth(max_width)

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.send_button.setEnabled(enabled)
        self.input.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)
        self.voice_button.setEnabled(enabled)
        self.input.setFocus() if enabled else None

    def closeEvent(self, event) -> None:
        if self.voice_engine.running:
            self.voice_engine.stop()

        if self.worker and self.worker.isRunning():
            self.worker.wait(3000)

        event.accept()


if __name__ == "__main__":
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    # This module normally receives its pipeline/voice objects from the
    # existing application entry point. It intentionally does not construct
    # backend components here.
    raise SystemExit("Run JARVIS through the existing application entry point.")

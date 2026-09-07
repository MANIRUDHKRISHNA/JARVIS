"""JARVIS system tray integration."""

from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class JarvisTray:
    """System-tray actions for showing, voicing, and exiting JARVIS."""

    def __init__(self, window):
        self.window = window
        self.tray = QSystemTrayIcon(QIcon(), window)
        self.menu = QMenu()

        show_action = QAction("Show JARVIS", self.menu)
        show_action.triggered.connect(self.show_window)
        self.menu.addAction(show_action)

        voice_action = QAction("Voice", self.menu)
        voice_action.triggered.connect(self.voice)
        self.menu.addAction(voice_action)

        self.menu.addSeparator()
        quit_action = QAction("Exit JARVIS", self.menu)
        quit_action.triggered.connect(self.quit)
        self.menu.addAction(quit_action)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._activated)

    def show(self):
        self.tray.show()

    def hide(self):
        self.tray.hide()

    def show_window(self):
        self.window.show()
        self.window.showNormal()
        self.window.activateWindow()
        self.window.raise_()

    def voice(self):
        self.show_window()
        self.window.voice_request()

    def quit(self):
        self.tray.hide()
        self.window.allow_close = True
        self.window.close()

    def _activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window()

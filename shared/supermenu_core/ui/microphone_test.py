"""A short microphone check; no audio storage or transcription service."""

import sys
from PySide6.QtCore import QTimer, QMicrophonePermission, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QProgressBar,
    QApplication,
)
from supermenu_core.audio.microphone import Microphone


class MicrophoneTest(QWidget):
    active_changed = Signal(bool)

    def __init__(self, device_id, parent=None):
        super().__init__(parent)
        self.device_id = device_id
        self.microphone = None
        self.generation = 0
        self.active = False
        self.received = False
        self.peak = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.button = QPushButton("Tester le micro")
        self.button.clicked.connect(self.toggle)
        row.addWidget(self.button)
        self.meter = QProgressBar()
        self.meter.setRange(0, 100)
        self.meter.setValue(0)
        self.meter.setTextVisible(False)
        self.meter.setFixedHeight(8)
        self.meter.setAccessibleName("Niveau du microphone en cours de test")
        row.addWidget(self.meter, 1)
        layout.addLayout(row)
        self.status = QLabel("Test de 5 secondes, sans enregistrement ni envoi audio.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.permission_button = QPushButton("Ouvrir les autorisations du microphone")
        self.permission_button.clicked.connect(self.open_permissions)
        self.permission_button.hide()
        layout.addWidget(self.permission_button)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.finish)
        QApplication.instance().aboutToQuit.connect(self.cancel)

    def open_permissions(self):
        url = (
            "ms-settings:privacy-microphone"
            if sys.platform == "win32"
            else "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"
        )
        QDesktopServices.openUrl(QUrl(url))

    def toggle(self):
        if self.active:
            self.cancel()
            return
        self.generation += 1
        generation = self.generation
        self.active = True
        self.active_changed.emit(True)
        self.button.setText("Arrêter le test")
        self.permission_button.hide()
        self.status.setText("Ouverture du microphone…")
        app = QApplication.instance()
        permission = QMicrophonePermission()
        status = app.checkPermission(permission)
        if status == Qt.PermissionStatus.Undetermined:
            self.status.setText("Autorisez le microphone dans la fenêtre du système.")
            app.requestPermission(
                permission,
                self,
                lambda result: self._permission(result.status(), generation),
            )
        else:
            self._permission(status, generation)

    def _permission(self, status, generation):
        if generation != self.generation or not self.active:
            return
        if status != Qt.PermissionStatus.Granted:
            self.failed(
                "L’accès au microphone est refusé. Autorisez SuperMenu dans les réglages du système."
            )
            return
        try:
            self.received, self.peak = False, 0
            mic = Microphone(16000, self.device_id(), self)
            self.microphone = mic
            mic.chunk.connect(self._received)
            mic.level.connect(self._level)
            mic.failed.connect(self.failed)
            mic.start()
            if self.microphone is not mic or not self.active:
                return
            self.status.setText("Microphone ouvert. Parlez : la barre doit bouger.")
            self.timer.start(5000)
        except Exception as exc:
            self.failed(str(exc))

    def _received(self, _pcm):
        self.received = True

    def _level(self, value):
        self.peak = max(self.peak, value)
        self.meter.setValue(value)

    def finish(self):
        received, peak = self.received, self.peak
        self.cancel(silent=True)
        self.status.setText(
            "Microphone opérationnel. Vous pouvez lancer une dictée."
            if received and peak > 0
            else (
                "Microphone ouvert, mais aucun son détecté. Vérifiez le bouton muet et le niveau d’entrée."
                if received
                else "Le microphone n’a fourni aucun audio. Vérifiez le périphérique et ses autorisations."
            )
        )

    def failed(self, message):
        self.cancel(silent=True)
        self.status.setText(message)
        self.permission_button.show()

    def cancel(self, *, silent=False):
        self.generation += 1
        self.active = False
        self.timer.stop()
        microphone, self.microphone = self.microphone, None
        if microphone is not None:
            microphone.stop()
            microphone.deleteLater()
        self.button.setText("Tester le micro")
        self.meter.setValue(0)
        self.active_changed.emit(False)
        if not silent:
            self.status.setText("Test arrêté. Aucun audio conservé.")

    def hideEvent(self, event):
        if self.active:
            self.cancel()
        super().hideEvent(event)

"""One live transcript surface for all speech engines and platforms."""

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from supermenu_core.audio.settings import MAX_DICTATION_SECONDS


class RecordingDialog(QDialog):
    recording_stopped = Signal()
    recording_cancelled = Signal()
    retry_requested = Signal()

    def __init__(self, parent=None, *, engine="Dictée", local=True):
        super().__init__(parent)
        self._state = "recording"
        self._action_emitted = False
        self._started_at = time.monotonic()
        self.setWindowTitle("Dictée SuperMenu")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setModal(False)
        self.resize(560, 430)
        self.setMinimumSize(420, 340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        heading = QHBoxLayout()
        self.title_label = QLabel("À l’écoute")
        font = self.title_label.font()
        font.setPointSize(16)
        font.setBold(True)
        self.title_label.setFont(font)
        heading.addWidget(self.title_label, 1)
        self.timer_label = QLabel("00:00")
        heading.addWidget(self.timer_label)
        layout.addLayout(heading)
        self.engine_label = QLabel(
            f"{engine} · {'Sur cet appareil' if local else 'Audio envoyé à OpenAI'}"
        )
        self.engine_label.setWordWrap(True)
        layout.addWidget(self.engine_label)
        self.hint_label = QLabel("Parlez : le texte apparaît au fur et à mesure.")
        self.hint_label.setWordWrap(True)
        self.hint_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.hint_label)
        self.transcript_edit = QPlainTextEdit()
        self.transcript_edit.setReadOnly(True)
        self.transcript_edit.setPlaceholderText("Votre transcription apparaîtra ici…")
        self.transcript_edit.setAccessibleName("Transcription en direct")
        self.transcript_edit.setMinimumHeight(140)
        layout.addWidget(self.transcript_edit, 1)
        meter = QHBoxLayout()
        meter.addWidget(QLabel("Microphone"))
        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setValue(0)
        self.level_bar.setTextVisible(False)
        self.level_bar.setFixedHeight(8)
        self.level_bar.setAccessibleName("Niveau du microphone")
        meter.addWidget(self.level_bar, 1)
        layout.addLayout(meter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        buttons = QHBoxLayout()
        self.copy_button = QPushButton("Copier")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_transcript)
        buttons.addWidget(self.copy_button)
        buttons.addStretch()
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        buttons.addWidget(self.cancel_button)
        self.stop_button = QPushButton("Terminer")
        self.stop_button.setDefault(True)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        buttons.addWidget(self.stop_button)
        layout.addLayout(buttons)
        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(250)
        self.animation_timer.timeout.connect(self._update_recording_ui)

    def showEvent(self, event):
        super().showEvent(event)
        if self._state == "recording":
            self.animation_timer.start()
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(
                area.center().x() - self.width() // 2,
                area.center().y() - self.height() // 2,
            )

    def closeEvent(self, event):
        self.animation_timer.stop()
        if self._state in {"recording", "preparing", "processing"}:
            self._request_cancel()
        super().closeEvent(event)

    def reject(self):
        self.animation_timer.stop()
        if self._state in {"recording", "preparing", "processing"}:
            self._request_cancel()
        super().reject()

    def _request_cancel(self):
        if self._state == "cancelled":
            return
        self._state = "cancelled"
        self.recording_cancelled.emit()

    def _on_cancel_clicked(self):
        self.reject()

    def _on_stop_clicked(self):
        if self._state == "error":
            self.retry_requested.emit()
        elif self._state == "recording" and not self._action_emitted:
            self._action_emitted = True
            self.set_processing("Finalisation de la transcription…")
            self.recording_stopped.emit()

    def _update_recording_ui(self):
        if self._state == "recording":
            elapsed = int(time.monotonic() - self._started_at)
            self.timer_label.setText(f"{elapsed // 60:02d}:{elapsed % 60:02d} / 05:00")
            if elapsed >= MAX_DICTATION_SECONDS:
                self._on_stop_clicked()

    def _title(self, title, status=""):
        self.title_label.setText(title)
        self.title_label.setProperty("status", status)
        self.title_label.style().unpolish(self.title_label)
        self.title_label.style().polish(self.title_label)

    def set_preparing(self, message="Préparation du moteur vocal…"):
        self._state = "preparing"
        self._action_emitted = False
        self.animation_timer.stop()
        self._title("Préparation…")
        self.hint_label.setText(message)
        self.transcript_edit.clear()
        self.copy_button.setEnabled(False)
        self.timer_label.setText("00:00")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        self.cancel_button.setText("Annuler")
        self.stop_button.setText("Terminer")
        self.stop_button.setEnabled(False)
        self.stop_button.show()

    def set_recording(self):
        self._state = "recording"
        self._started_at = time.monotonic()
        self._title("À l’écoute", "success")
        self.hint_label.setText(
            "Parlez : le texte apparaît au fur et à mesure. Terminez pour obtenir le résultat final."
        )
        self.progress_bar.hide()
        self.stop_button.setEnabled(True)
        self.animation_timer.start()

    def set_transcript(self, text):
        bar = self.transcript_edit.verticalScrollBar()
        follow = bar.value() >= bar.maximum() - 4
        position = bar.value()
        self.transcript_edit.setPlainText(text)
        bar.setValue(bar.maximum() if follow else position)
        self.copy_button.setEnabled(bool(text.strip()))

    def copy_transcript(self):
        QApplication.clipboard().setText(self.transcript_edit.toPlainText())
        self.copy_button.setText("Copié")
        QTimer.singleShot(1000, lambda: self.copy_button.setText("Copier"))

    def set_processing(self, message):
        self._state = "processing"
        self.animation_timer.stop()
        self._title("Finalisation…")
        self.hint_label.setText(message)
        self.level_bar.setValue(0)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        self.stop_button.setEnabled(False)

    def set_success(self, message):
        self._state = "success"
        self.animation_timer.stop()
        self._title("Transcription terminée", "success")
        self.hint_label.setText(message)
        self.progress_bar.hide()
        self.stop_button.hide()
        self.cancel_button.setText("Fermer")

    def set_error(self, message):
        self._state = "error"
        self.animation_timer.stop()
        self._title("Dictée interrompue", "error")
        self.hint_label.setText(message)
        self.progress_bar.hide()
        self.level_bar.setValue(0)
        self.stop_button.setText("Réessayer")
        self.stop_button.setEnabled(True)
        self.stop_button.show()
        self.cancel_button.setText("Fermer")

    def dismiss(self):
        self._state = "closed"
        self.close()

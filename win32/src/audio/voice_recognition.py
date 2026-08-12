#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Enregistrement vocal, transcription et retour visuel non bloquant."""

import logging
import os
import threading
import time

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from src.audio.audio_config import MAX_RECORDING_TIME
from src.audio.audio_recorder import AudioRecorder
from src.audio.transcription import Transcriber, TranscriptionError
from src.utils.logger import log
from src.utils.safe_dialogs import SafeDialogs
from src.utils.text_inserter import TextInserter


class RecordingDialog(QDialog):
    """Carte d'enregistrement qui reste utile pendant toute la transcription."""

    recording_stopped = Signal()
    recording_cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "recording"
        self._action_emitted = False
        self._started_at = time.monotonic()
        self._pulse_visible = True

        self.setWindowTitle("Dictée SuperMenu")
        self.setWindowFlags(
            Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
        )
        self.setModal(False)
        self.setMinimumWidth(390)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #20242b;
                border: 1px solid #434b57;
                border-radius: 12px;
            }
            QLabel {
                color: #f4f6f8;
                background: transparent;
            }
            QLabel#recordingTitle {
                font-size: 14pt;
                font-weight: 700;
            }
            QLabel#recordingHint {
                color: #b9c0ca;
                font-size: 10pt;
            }
            QLabel#recordingTimer {
                color: #ff6b6b;
                font-size: 11pt;
                font-weight: 600;
            }
            QProgressBar {
                min-height: 8px;
                max-height: 8px;
                border: none;
                border-radius: 4px;
                background: #343a44;
                text-align: center;
            }
            QProgressBar::chunk {
                border-radius: 4px;
                background: #ff5d5d;
            }
            QPushButton {
                border: 1px solid #525b68;
                border-radius: 7px;
                padding: 9px 14px;
                color: #f4f6f8;
                background: #303640;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #3a424e;
            }
            QPushButton#finishRecording {
                background: #d94b4b;
                border-color: #e85c5c;
            }
            QPushButton#finishRecording:hover {
                background: #ea5757;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        self.title_label = QLabel("●  Enregistrement en cours")
        self.title_label.setObjectName("recordingTitle")
        layout.addWidget(self.title_label)

        self.hint_label = QLabel(
            "Parlez normalement, puis terminez l'enregistrement quand votre "
            "dictée est prête."
        )
        self.hint_label.setObjectName("recordingHint")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        self.timer_label = QLabel()
        self.timer_label.setObjectName("recordingTimer")
        self.timer_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.timer_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, MAX_RECORDING_TIME)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        buttons.addWidget(self.cancel_button)

        self.stop_button = QPushButton("Terminer et transcrire")
        self.stop_button.setObjectName("finishRecording")
        self.stop_button.setDefault(True)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        buttons.addWidget(self.stop_button)
        layout.addLayout(buttons)

        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(250)
        self.animation_timer.timeout.connect(self._update_recording_ui)
        self._update_recording_ui()

    def showEvent(self, event):
        super().showEvent(event)
        self.animation_timer.start()
        screen = QApplication.screenAt(QCursor.pos())
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.adjustSize()
            self.move(
                area.center().x() - self.width() // 2,
                area.center().y() - self.height() // 2,
            )

    def closeEvent(self, event):
        self.animation_timer.stop()
        if self._state == "recording" and not self._action_emitted:
            self._request_cancel()
        super().closeEvent(event)

    @staticmethod
    def _format_duration(seconds):
        seconds = max(0, int(seconds))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def _update_recording_ui(self):
        if self._state != "recording":
            return
        elapsed = min(
            MAX_RECORDING_TIME,
            int(time.monotonic() - self._started_at),
        )
        self.progress_bar.setValue(elapsed)
        self.timer_label.setText(
            f"{self._format_duration(elapsed)} / "
            f"{self._format_duration(MAX_RECORDING_TIME)}"
        )
        self._pulse_visible = not self._pulse_visible
        marker = "●" if self._pulse_visible else "○"
        self.title_label.setText(f"{marker}  Enregistrement en cours")

    def _on_stop_clicked(self):
        if self._state != "recording" or self._action_emitted:
            return
        self._action_emitted = True
        self.set_processing("Préparation de l'enregistrement…")
        self.recording_stopped.emit()

    def _on_cancel_clicked(self):
        if self._state == "recording":
            self._request_cancel()
        self.close()

    def _request_cancel(self):
        if self._action_emitted:
            return
        self._action_emitted = True
        self.recording_cancelled.emit()

    def dismiss(self):
        """Fermer sans convertir la fermeture en nouvelle action utilisateur."""
        self._action_emitted = True
        self.close()

    def set_processing(self, message):
        self._state = "processing"
        self.animation_timer.stop()
        self.title_label.setText("✨  Transcription")
        self.hint_label.setText(message)
        self.timer_label.setText("Traitement sécurisé en arrière-plan")
        self.progress_bar.setRange(0, 0)
        self.stop_button.setVisible(False)
        self.cancel_button.setText("Masquer")

    def set_success(self, message):
        self._state = "success"
        self.title_label.setText("✓  Transcription terminée")
        self.hint_label.setText(message)
        self.timer_label.clear()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setStyleSheet(
            "QProgressBar::chunk { background: #44b678; }"
        )
        self.stop_button.setVisible(False)
        self.cancel_button.setText("Fermer")
        QTimer.singleShot(1400, self.dismiss)

    def set_error(self, message):
        self._state = "error"
        self.title_label.setText("⚠  Transcription impossible")
        self.hint_label.setText(message)
        self.timer_label.clear()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.stop_button.setVisible(False)
        self.cancel_button.setText("Fermer")


class VoiceRecognition(QObject):
    """Orchestrer une dictée complète sans bloquer le thread Qt."""

    _callback_signal = Signal(str)
    _insert_signal = Signal(str, object)
    _processing_signal = Signal(str)
    _success_signal = Signal(str)
    _error_signal = Signal(str)

    def __init__(
        self,
        api_key=None,
        microphone_index=None,
        callback=None,
        target=None,
        *,
        transcription_languages=None,
        transcription_prompt="",
        transcription_keywords=None,
        callback_success_message=(
            "Le texte a été transcrit. Le traitement IA est lancé."
        ),
    ):
        super().__init__()
        self.api_key = api_key
        self.microphone_index = microphone_index
        self.callback = callback
        self.callback_success_message = callback_success_message
        self.target = target
        self.recorder = AudioRecorder(
            input_device_index=microphone_index
        )
        self.transcriber = Transcriber(
            api_key=api_key,
            languages=transcription_languages,
            prompt=transcription_prompt,
            keywords=transcription_keywords,
        )
        self.text_inserter = TextInserter()
        self.is_recording = False
        self.is_processing = False
        self.recording_file = None
        self._insert_text_after_recording = True
        self.recording_dialog = None
        self._cancel_event = threading.Event()
        self._worker_thread = None
        self._cleanup_lock = threading.Lock()
        self._resources_cleaned = False

        self.recording_timeout_timer = QTimer(self)
        self.recording_timeout_timer.setSingleShot(True)
        self.recording_timeout_timer.timeout.connect(
            self._finish_recording
        )

        self._insert_signal.connect(self._insert_transcription_impl)
        self._callback_signal.connect(self._dispatch_callback)
        self._processing_signal.connect(self._show_processing)
        self._success_signal.connect(self._show_success)
        self._error_signal.connect(self._show_error)
        log("Module de reconnaissance vocale initialisé")

    @staticmethod
    def list_microphones():
        return AudioRecorder.list_microphones()

    def start_voice_recognition(self, insert_text=True):
        if self.is_recording or self.is_processing:
            log("Une session vocale est déjà en cours")
            return False

        try:
            app = QApplication.instance()
            if app is not None:
                app.beep()

            self._cancel_event.clear()
            self._insert_text_after_recording = insert_text
            self.recording_file = self.recorder.start_recording()
            if not self.recording_file:
                raise TranscriptionError(
                    "Impossible d'ouvrir le microphone sélectionné."
                )

            self.is_recording = True
            self.recording_dialog = RecordingDialog()
            self.recording_dialog.recording_stopped.connect(
                self._finish_recording
            )
            self.recording_dialog.recording_cancelled.connect(
                self._cancel_recording
            )
            self.recording_dialog.show()
            self.recording_timeout_timer.start(
                MAX_RECORDING_TIME * 1000
            )
            log("Début de l'enregistrement vocal")
            return True
        except Exception as exc:
            self.is_recording = False
            self._cleanup_recorder()
            message = (
                str(exc)
                if isinstance(exc, TranscriptionError)
                else f"Impossible de démarrer l'enregistrement : {exc}"
            )
            SafeDialogs.show_critical(
                "Erreur de reconnaissance vocale",
                message,
            )
            return False

    @Slot()
    def _finish_recording(self):
        if not self.is_recording:
            return

        self.is_recording = False
        self.is_processing = True
        self.recording_timeout_timer.stop()
        self._show_processing("Préparation de l'enregistrement…")

        app = QApplication.instance()
        if app is not None:
            app.beep()

        insert_text = self._insert_text_after_recording

        def process_audio():
            audio_file = None
            try:
                audio_file = self.recorder.stop_recording()
                if self._cancel_event.is_set():
                    return
                if not audio_file or not os.path.isfile(audio_file):
                    raise TranscriptionError(
                        "Aucun son exploitable n'a été enregistré."
                    )

                self._processing_signal.emit(
                    "Transcription avec GPT Transcribe…"
                )
                text = self.transcriber.transcribe(audio_file)
                if self._cancel_event.is_set():
                    return

                if self.callback and callable(self.callback):
                    self._callback_signal.emit(text)
                    self._success_signal.emit(self.callback_success_message)
                elif insert_text:
                    self._insert_signal.emit(text, self.target)
                else:
                    self._success_signal.emit(
                        "Le texte a été transcrit avec succès."
                    )
            except TranscriptionError as exc:
                if not self._cancel_event.is_set():
                    log(str(exc), logging.ERROR)
                    self._error_signal.emit(str(exc))
            except Exception as exc:
                if not self._cancel_event.is_set():
                    log(
                        f"Erreur inattendue pendant la transcription: {exc}",
                        logging.ERROR,
                    )
                    self._error_signal.emit(
                        "Une erreur inattendue est survenue pendant la "
                        "transcription."
                    )
            finally:
                if audio_file and os.path.exists(audio_file):
                    try:
                        os.remove(audio_file)
                    except OSError as exc:
                        log(
                            "Impossible de supprimer le fichier audio "
                            f"temporaire : {exc}",
                            logging.WARNING,
                        )
                self.is_processing = False
                self._cleanup_recorder()

        self._worker_thread = threading.Thread(
            target=process_audio,
            name="SuperMenuAudioTranscription",
            daemon=True,
        )
        self._worker_thread.start()

    @Slot()
    def _cancel_recording(self):
        self._cancel_event.set()
        self.recording_timeout_timer.stop()
        if not self.is_recording:
            return

        self.is_recording = False
        self.recorder.cancel_recording()
        self._cleanup_recorder()
        log("Enregistrement vocal annulé", logging.INFO)

    @Slot(str)
    def _dispatch_callback(self, text):
        if self._cancel_event.is_set():
            return
        try:
            if self.callback and callable(self.callback):
                self.callback(text)
        except Exception as exc:
            log(
                f"Erreur lors du traitement de la transcription: {exc}",
                logging.ERROR,
            )
            self._show_error(
                "La transcription a réussi, mais son traitement a échoué."
            )

    @Slot(str, object)
    def _insert_transcription_impl(self, text, target):
        if self._cancel_event.is_set():
            return
        if self.text_inserter.insert_text(text, target=target):
            self._show_success(
                "La transcription a été insérée dans le champ sélectionné."
            )
            return

        self._show_error(
            "La transcription est prête, mais la fenêtre cible a changé. "
            "Le texte n'a pas été collé."
        )

    @Slot(str)
    def _show_processing(self, message):
        dialog = self.recording_dialog
        if dialog is not None:
            dialog.set_processing(message)

    @Slot(str)
    def _show_success(self, message):
        dialog = self.recording_dialog
        if dialog is not None and dialog.isVisible():
            dialog.set_success(message)

    @Slot(str)
    def _show_error(self, message):
        dialog = self.recording_dialog
        if dialog is not None and dialog.isVisible():
            dialog.set_error(message)
        else:
            SafeDialogs.show_critical(
                "Erreur de reconnaissance vocale",
                message,
            )

    def _cleanup_recorder(self):
        with self._cleanup_lock:
            if self._resources_cleaned:
                return
            self._resources_cleaned = True
        self.recorder.cleanup()

    def cleanup(self):
        """Annuler les effets futurs et libérer le microphone."""
        if self.is_recording or self.is_processing:
            self._cancel_event.set()
        self.recording_timeout_timer.stop()

        dialog = self.recording_dialog
        if dialog is not None and dialog.isVisible():
            dialog.dismiss()

        if self.is_recording:
            self.is_recording = False
            self.recorder.cancel_recording()
            self._cleanup_recorder()
        elif not self.is_processing:
            self._cleanup_recorder()

        log("Ressources de reconnaissance vocale nettoyées")

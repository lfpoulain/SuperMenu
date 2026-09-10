"""Capture only when the chosen engine is ready; ignore every late result."""

from PySide6.QtCore import QMicrophonePermission, QObject, Qt
from PySide6.QtWidgets import QApplication

from .microphone import Microphone
from supermenu_core.ui.dictation_dialog import RecordingDialog


class DictationSession(QObject):
    def __init__(self, backend_factory, options, callback=None, parent=None):
        super().__init__(parent)
        self.backend_factory = backend_factory
        self.options = dict(options)
        self.callback = callback
        self.backend = None
        self.microphone = None
        self.recording_dialog = None
        self.is_recording = False
        self.is_processing = False
        self._generation = 0
        self._cancelled = False

    def start_voice_recognition(self):
        if self.is_recording or self.is_processing:
            return False
        provider = self.options["provider"]
        label = {
            "openai": "OpenAI · GPT Live Transcribe",
            "foundry": "Foundry Local · Nemotron 3.5",
            "apple": "Apple Speech",
        }[provider]
        self.recording_dialog = RecordingDialog(
            engine=label, local=provider != "openai"
        )
        self.recording_dialog.recording_stopped.connect(self.finish)
        self.recording_dialog.recording_cancelled.connect(self.cancel)
        self.recording_dialog.retry_requested.connect(self._start)
        self._configure_dialog()
        self.recording_dialog.set_preparing()
        self.recording_dialog.show()
        self._start()
        return True

    def _configure_dialog(self):
        """Allow plain dictation to add delivery actions to this same surface."""

    def stop_listening(self):
        if self.is_recording:
            self.finish()
        elif self.is_processing and self.microphone is None:
            # Releasing a held shortcut during model loading must never start
            # the microphone later, including after a permission response.
            self.cancel()
            if self.recording_dialog:
                self.recording_dialog.dismiss()

    def _start(self):
        self._release()
        self._cancelled = False
        self._generation += 1
        generation = self._generation
        self.is_processing = True
        self.recording_dialog.set_preparing()
        try:
            self.backend = self.backend_factory(self.options)
            backend = self.backend

            def current(function):
                def dispatch(*args):
                    if generation == self._generation and not self._cancelled:
                        function(*args)

                return dispatch

            backend.ready.connect(current(self._ready))
            backend.transcript.connect(current(self.recording_dialog.set_transcript))
            backend.completed.connect(current(self._completed))
            backend.failed.connect(current(self._error))
            backend.progress.connect(current(self._progress))
            backend.start()
        except Exception as exc:
            self._error(str(exc))

    def _progress(self, message, _percent):
        titles = {
            "verify": "Vérification…",
            "hardware": "Activation du GPU…",
            "load": "Chargement en mémoire…",
            "download": "Téléchargement…",
            "connect": "Connexion…",
            "reuse": "Modèle déjà en mémoire",
        }
        self.recording_dialog._title(titles.get(self.backend.phase, "Préparation…"))
        self.recording_dialog.hint_label.setText(message)

    def _ready(self):
        if self.microphone is not None:
            return
        app = QApplication.instance()
        permission = QMicrophonePermission()
        status = app.checkPermission(permission)
        if status == Qt.PermissionStatus.Undetermined:
            self.recording_dialog.hint_label.setText(
                "Autorisez SuperMenu à utiliser le microphone pour commencer."
            )
            generation = self._generation
            app.requestPermission(
                permission,
                self,
                lambda granted: self._permission_result(granted, generation),
            )
        elif status == Qt.PermissionStatus.Denied:
            self._error(
                "Le microphone n’est pas autorisé. Activez l’accès au microphone pour SuperMenu dans les réglages système."
            )
        else:
            self._start_microphone()

    def _permission_result(self, permission, generation):
        if self._cancelled or generation != self._generation:
            return
        if permission.status() == Qt.PermissionStatus.Granted:
            self._start_microphone()
        else:
            self._error(
                "L’accès au microphone a été refusé. Autorisez-le dans les réglages système puis réessayez."
            )

    def _start_microphone(self):
        if self._cancelled or self.backend is None or self.microphone is not None:
            return
        try:
            self.microphone = Microphone(
                self.backend.sample_rate, self.options.get("microphone", ""), self
            )
            self.microphone.chunk.connect(self.backend.append)
            self.microphone.level.connect(self.recording_dialog.level_bar.setValue)
            self.microphone.failed.connect(self._error)
            microphone = self.microphone
            microphone.start()
            if self.microphone is not microphone or self.backend is None:
                return
            self.is_recording, self.is_processing = True, False
            self.recording_dialog.set_recording()
        except Exception as exc:
            self._error(str(exc))

    def finish(self):
        if not self.is_recording or self._cancelled:
            return
        self.is_recording, self.is_processing = False, True
        self.recording_dialog.set_processing(
            "Le microphone est arrêté. Les derniers mots sont en cours de finalisation…"
        )
        if self.microphone:
            self.microphone.stop(flush=True)
        if not self._cancelled and self.backend is not None and self.is_processing:
            self.backend.finish()

    def _completed(self, text):
        self.is_processing = self.is_recording = False
        self._generation += 1
        self._release()
        if not text.strip():
            self.recording_dialog.set_error(
                "Aucune parole détectée. Vérifiez le niveau du microphone et réessayez."
            )
            return
        self.recording_dialog.set_transcript(text)
        self.recording_dialog.set_success(
            "Votre texte est prêt. Vous pouvez le copier."
        )
        if self.callback:
            try:
                self.callback(text)
                self.recording_dialog.dismiss()
            except Exception:
                self.recording_dialog.set_error(
                    "La transcription a réussi, mais son traitement a échoué. Vous pouvez copier le texte."
                )

    def _error(self, message):
        if self._cancelled:
            return
        self.is_recording = self.is_processing = False
        self._generation += 1
        self._release()
        self.recording_dialog.set_error(message)

    def _release(self):
        microphone, self.microphone = self.microphone, None
        if microphone:
            microphone.stop()
            microphone.deleteLater()
        backend, self.backend = self.backend, None
        if backend:
            backend.cancel()
            backend.deleteLater()

    def cancel(self):
        self._cancelled = True
        self._generation += 1
        self.is_recording = self.is_processing = False
        self._release()

    def cleanup(self):
        self.cancel()
        if self.recording_dialog:
            self.recording_dialog.dismiss()
            self.recording_dialog.deleteLater()
            self.recording_dialog = None

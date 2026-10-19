import sys
import time
from pathlib import Path

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from supermenu_core.audio import resident
from supermenu_core.audio.settings import SpeechSettingsMixin
from PySide6.QtCore import QSettings


def wait_for(predicate, seconds=5):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate()


@pytest.fixture
def service(monkeypatch):
    app = QApplication.instance() or QApplication([])
    service = resident.ResidentSpeechService(app)
    monkeypatch.setattr(resident, "get_resident_service", lambda: service)
    yield service
    service.close()


def backend(text, idle=300, **options):
    command = (
        sys.executable,
        [str(Path(__file__).parent / "helpers" / "resident_voice_worker.py")],
    )
    return resident.ResidentSpeechBackend(
        command,
        {"provider": "foundry", "language": "fr", "text": text, **options},
        idle,
    )


def start(lease):
    ready = []
    lease.ready.connect(lambda: ready.append(True))
    lease.start()
    wait_for(lambda: bool(ready))


def finish(lease):
    results = []
    lease.completed.connect(results.append)
    lease.finish()
    wait_for(lambda: bool(results))
    return results


def test_successive_dictations_reuse_worker_without_reusing_transcript(service):
    first = backend("Première dictée")
    start(first)
    process = service.process
    pid = process.processId()
    assert finish(first) == ["Première dictée"]
    first.cancel()  # DictationSession always releases its completed lease.
    assert service.loaded and not service.busy
    second = backend("Deuxième dictée")
    updates = []
    second.transcript.connect(updates.append)
    start(second)
    second.append(b"\x00\x00")
    assert finish(second) == ["Deuxième dictée"]
    assert updates == ["Deuxième dictée"]
    assert service.process is process and process.processId() == pid
    assert service.unload_idle()
    assert service.process is None and not service.loaded


def test_cancel_and_immediate_reopen_wait_for_clean_native_session(service):
    first = backend("À ignorer")
    start(first)
    process = service.process
    first.cancel()
    second = backend("À conserver")
    ready = []
    second.ready.connect(lambda: ready.append(True))
    second.start()
    assert service.pending is second
    wait_for(lambda: bool(ready))
    assert service.process is process
    assert not service.unload_idle()
    assert finish(second) == ["À conserver"]


def test_idle_timeout_starts_after_dictation_not_during_recording(service):
    lease = backend("Texte", idle=1)
    start(lease)
    assert not service.idle_timer.isActive()
    assert finish(lease) == ["Texte"]
    assert service.idle_timer.isActive()
    wait_for(lambda: service.process is None)
    assert not service.loaded


@pytest.mark.parametrize("idle, retained", [(0, False), (-1, True)])
def test_immediate_and_until_app_exit_policies(service, idle, retained):
    lease = backend("Texte", idle=idle)
    start(lease)
    finish(lease)
    assert service.loaded == retained
    assert not service.idle_timer.isActive()
    service.close()
    assert service.process is None


def test_changing_language_restarts_worker_and_errors_release_memory(service):
    first = backend("Français")
    start(first)
    process = service.process
    finish(first)
    second = backend("English", language="en")
    errors = []
    second.failed.connect(errors.append)
    start(second)
    assert service.process is not process
    service.process.kill()
    wait_for(lambda: bool(errors))
    assert len(errors) == 1
    assert service.process is None and not service.loaded
    third = backend("Reprise")
    start(third)
    assert finish(third) == ["Reprise"]


def test_setting_persists_and_invalid_legacy_value_uses_default(tmp_path):
    settings = SpeechSettingsMixin()
    path = str(tmp_path / "settings.ini")
    settings.settings = QSettings(path, QSettings.Format.IniFormat)
    assert settings.get_speech_idle_seconds() == 300
    settings.set_speech_idle_seconds(-1)
    settings.settings.sync()
    settings.settings = QSettings(path, QSettings.Format.IniFormat)
    assert settings.get_speech_idle_seconds() == -1
    settings.settings.setValue("speech_idle_seconds", "bad")
    assert settings.get_speech_idle_seconds() == 300


def test_settings_save_policy_and_disable_unload_during_dictation(
    service, tmp_path, monkeypatch
):
    from supermenu_core.ui import speech_settings

    settings = SpeechSettingsMixin()
    settings.settings = QSettings(
        str(tmp_path / "voice.ini"), QSettings.Format.IniFormat
    )
    settings.get_api_key = lambda: ""
    settings.sync = settings.settings.sync
    settings.set_speech_provider("foundry")
    monkeypatch.setattr(speech_settings, "get_resident_service", lambda: service)
    widget = speech_settings.SpeechSettingsWidget(
        settings, lambda _: None, platform="win32"
    )
    widget.idle_combo.setCurrentIndex(widget.idle_combo.findData(60))
    assert widget.save()
    assert settings.get_speech_idle_seconds() == 60
    assert service.idle_seconds == 60
    lease = backend("Bonjour", idle=60)
    start(lease)
    assert not widget.unload_button.isEnabled()
    finish(lease)
    assert widget.unload_button.isEnabled()
    widget.unload_button.click()
    assert service.process is None and not widget.unload_button.isEnabled()

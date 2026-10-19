"""Resident voice service: deadlines, worker-level errors and draining."""

import sys
import time
from pathlib import Path

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from supermenu_core.audio import resident
from supermenu_core.audio.backends import LONG_TIMEOUT_MS, START_TIMEOUT_MS


def wait_for(predicate, seconds=10):
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


def lease(text="", mode="", **options):
    command = (
        sys.executable,
        [str(Path(__file__).parent / "helpers" / "resident_voice_worker.py")],
    )
    backend = resident.ResidentSpeechBackend(
        command,
        {"provider": "foundry", "language": "fr", "text": text, "mode": mode, **options},
        300,
    )
    backend.events = {"failed": [], "ready": [], "completed": [], "progress": []}
    backend.failed.connect(backend.events["failed"].append)
    backend.completed.connect(backend.events["completed"].append)
    backend.ready.connect(lambda: backend.events["ready"].append(True))
    return backend


def test_gpu_activation_extends_the_startup_deadline(service):
    backend = lease("Bonjour", mode="hardware")
    backend.progress.connect(
        lambda _message, _percent: backend.events["progress"].append(
            (backend.phase, service.timer.interval())
        )
    )
    backend.start()
    assert service.timer.interval() == START_TIMEOUT_MS
    wait_for(lambda: backend.events["ready"])
    assert backend.events["progress"] == [
        ("verify", START_TIMEOUT_MS),
        ("hardware", LONG_TIMEOUT_MS),
        ("load", START_TIMEOUT_MS),
    ]
    assert not service.timer.isActive()
    backend.finish()
    wait_for(lambda: backend.events["completed"])
    assert backend.events["completed"] == ["Bonjour"]


def test_progress_after_ready_never_arms_a_deadline_during_recording(service):
    backend = lease("Bonjour", mode="late_progress")
    backend.progress.connect(
        lambda *_args: backend.events["progress"].append(service.timer.isActive())
    )
    backend.start()
    wait_for(lambda: backend.events["progress"])
    assert backend.events["progress"] == [False]
    assert not service.timer.isActive()
    backend.cancel()


def test_worker_error_without_session_reaches_the_active_dictation(service):
    message = (
        "Foundry n’a pas pu terminer la dictée. Vérifiez la disponibilité du "
        "modèle, la mémoire et les pilotes GPU."
    )
    backend = lease(message, mode="sessionless_error")
    backend.start()
    wait_for(lambda: backend.events["failed"])
    QTest.qWait(100)
    assert backend.events["failed"] == [message]
    assert service.process is None and not service.busy


def test_startup_deadline_fails_the_dictation(service):
    backend = lease(mode="silent")
    backend.start()
    service.timer.start(1)
    wait_for(lambda: backend.events["failed"])
    assert backend.events["failed"] == [
        "Le moteur vocal n’a pas répondu à temps. Réessayez."
    ]
    assert service.process is None


@pytest.mark.parametrize(
    "mode", ["drain_error", "drain_sessionless_error", "drain_exit", "drain_silent"]
)
def test_failed_drain_restarts_the_waiting_dictation(service, mode):
    first = lease("À ignorer", mode=mode)
    first.start()
    wait_for(lambda: first.events["ready"])
    process = service.process
    first.cancel()
    assert service.draining == first.session_id
    second = lease("À conserver")
    second.start()
    assert service.pending is second
    if mode == "drain_silent":
        service.timer.start(1)  # The 15 s drain deadline expires.
    wait_for(lambda: second.events["ready"] or second.events["failed"])
    assert not second.events["failed"]
    assert service.process is not None and service.process is not process
    second.finish()
    wait_for(lambda: second.events["completed"])
    assert second.events["completed"] == ["À conserver"]
    assert not first.events["failed"]


def test_failed_drain_without_waiting_dictation_only_unloads(service):
    first = lease("À ignorer", mode="drain_error")
    first.start()
    wait_for(lambda: first.events["ready"])
    first.cancel()
    wait_for(lambda: service.process is None)
    assert not service.busy and not service.loaded
    assert not first.events["failed"]

"""ProcessSpeechBackend against a real child process (probe/download path)."""

import sys
import time
from pathlib import Path

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from supermenu_core.audio.backends import (
    LONG_TIMEOUT_MS,
    START_TIMEOUT_MS,
    ProcessSpeechBackend,
    startup_timeout,
)

WORKER = Path(__file__).parent / "helpers" / "process_voice_worker.py"


def wait_for(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate()


@pytest.fixture
def run():
    QApplication.instance() or QApplication([])
    backends = []

    def launch(mode, action="probe", command=None):
        backend = ProcessSpeechBackend(
            command or (sys.executable, [str(WORKER)]),
            {"provider": "foundry", "action": action, "mode": mode},
        )
        events = {"failed": [], "result": [], "progress": [], "ready": []}
        backend.failed.connect(events["failed"].append)
        backend.result.connect(events["result"].append)
        backend.ready.connect(lambda: events["ready"].append(True))
        # The deadline is re-armed before progress is emitted.
        backend.progress.connect(
            lambda _message, _percent: events["progress"].append(
                (backend.phase, backend.timer.interval())
            )
        )
        backends.append(backend)
        backend.start()
        return backend, events

    yield launch
    for backend in backends:
        backend.cancel()


def test_startup_timeout_only_extends_blocking_phases():
    assert startup_timeout("hardware") == LONG_TIMEOUT_MS
    assert startup_timeout("download") == LONG_TIMEOUT_MS
    assert startup_timeout("verify") == START_TIMEOUT_MS
    assert startup_timeout("verify", LONG_TIMEOUT_MS) == LONG_TIMEOUT_MS


def test_probe_gpu_activation_gets_long_deadline_then_reports_result(run):
    backend, events = run("result")
    wait_for(lambda: events["result"])
    assert events["result"] == [{"cached": True, "device": "CPU"}]
    assert events["progress"] == [
        ("verify", START_TIMEOUT_MS),
        ("hardware", LONG_TIMEOUT_MS),
    ]
    assert not events["failed"] and not backend.timer.isActive()


def test_download_keeps_its_long_deadline_for_every_step(run):
    _backend, events = run("result", action="download")
    wait_for(lambda: events["result"])
    assert [interval for _phase, interval in events["progress"]] == [
        LONG_TIMEOUT_MS,
        LONG_TIMEOUT_MS,
    ]


def test_worker_error_message_reaches_settings_once(run):
    _backend, events = run("error")
    wait_for(lambda: events["failed"])
    QTest.qWait(100)
    assert events["failed"] == ["Nemotron n’est pas disponible."]


def test_exit_without_answer_is_reported_as_early_stop(run):
    _backend, events = run("exit")
    wait_for(lambda: events["failed"])
    QTest.qWait(100)
    assert events["failed"] == [
        "Le moteur vocal s’est arrêté avant la fin de la transcription."
    ]


def test_crash_is_not_reported_as_an_installation_problem(run):
    _backend, events = run("crash", action="download")
    wait_for(lambda: events["failed"])
    QTest.qWait(100)
    assert events["failed"] == [
        "Le moteur vocal s’est arrêté avant la fin de la transcription."
    ]


def test_crash_keeps_the_worker_last_error_message(run):
    _backend, events = run("error_then_crash")
    wait_for(lambda: events["failed"])
    QTest.qWait(100)
    assert events["failed"] == ["Mémoire insuffisante."]


def test_missing_program_is_reported_as_start_failure(run, tmp_path):
    _backend, events = run(
        "result", command=(str(tmp_path / "supermenu-voice-absent"), [])
    )
    wait_for(lambda: events["failed"])
    QTest.qWait(100)
    assert events["failed"] == ["Le moteur vocal local n’a pas pu démarrer."]


@pytest.mark.parametrize("mode", ["invalid", "flood"])
def test_invalid_or_oversized_output_is_rejected(run, mode):
    backend, events = run(mode)
    wait_for(lambda: events["failed"])
    QTest.qWait(100)
    assert events["failed"] == ["Réponse invalide du moteur vocal."]
    assert backend.closed


def test_progress_after_ready_never_arms_a_deadline_during_recording(run):
    backend, events = run("ready", action="start")
    wait_for(lambda: events["progress"])
    assert events["ready"] == [True]
    assert not backend.timer.isActive()
    completed = []
    backend.completed.connect(completed.append)
    backend.finish()
    assert backend.timer.interval() == 60_000
    wait_for(lambda: completed)
    assert completed == ["Bonjour"] and not events["failed"]


def test_backpressure_fails_instead_of_buffering_audio(run, monkeypatch):
    backend, events = run("ready", action="start")
    wait_for(lambda: events["ready"])
    monkeypatch.setattr(backend.process, "bytesToWrite", lambda: 3_000_000)
    backend.append(b"\x00\x00")
    assert events["failed"] == [
        "Le moteur vocal ne suit plus le microphone. Arrêtez les tâches lourdes et réessayez."
    ]

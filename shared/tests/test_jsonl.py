"""JSON-lines framing shared by the private worker supervisors."""

import json
import sys
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QProcess
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from supermenu_core.audio.backends import ProcessSpeechBackend, configure_worker_process
from supermenu_core.utils.jsonl import JsonLineBuffer, encode_json_line

ONE_SHOT_WORKER = Path(__file__).parent / "helpers" / "one_shot_voice_worker.py"


def test_requests_are_single_utf8_json_lines():
    message = {"text": "Été — ok", "audio": "AAE="}

    # Same bytes as the voice supervisors (ASCII) and the Foundry one (UTF-8).
    assert encode_json_line(message) == (json.dumps(message) + "\n").encode("utf-8")
    assert encode_json_line(message).isascii()
    assert encode_json_line(message, ensure_ascii=False) == (
        json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n"
    )


def test_lines_are_reassembled_across_chunks():
    lines = JsonLineBuffer(max_bytes=1000)
    lines.feed(b'{"a": ')
    assert not lines.has_line()

    lines.feed(bytearray(b'1}\r\n\n{"b": 2}\n{"c"'))
    popped = []
    while lines.has_line():
        popped.append(lines.pop_line())

    # Only the newline is removed: json.loads ignores the CR, as before.
    assert popped == [b'{"a": 1}\r', b"", b'{"b": 2}']
    assert lines.data == b'{"c"'
    lines.clear()
    assert lines.data == b"" and not lines.has_line()


def test_overflow_counts_every_pending_byte():
    lines = JsonLineBuffer(max_bytes=4)
    lines.feed(b"1\n2\n")
    assert not lines.overflowed
    lines.feed(b"3")
    assert lines.overflowed


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_voice_workers_get_utf8_pipes_and_the_running_extraction(app, monkeypatch):
    monkeypatch.setenv("PYINSTALLER_RESET_ENVIRONMENT", "1")
    process = QProcess()

    configure_worker_process(process)

    environment = process.processEnvironment()
    assert environment.value("PYTHONIOENCODING") == "utf-8"
    assert not environment.contains("PYINSTALLER_RESET_ENVIRONMENT")


def test_one_shot_worker_reads_split_and_crlf_lines(app):
    options = {"action": "probe", "device": "auto", "prompt": "Été"}
    backend = ProcessSpeechBackend((sys.executable, [str(ONE_SHOT_WORKER)]), options)
    events = []
    backend.progress.connect(lambda message, percent: events.append(("progress", message, percent)))
    backend.transcript.connect(lambda text: events.append(("transcript", text)))
    backend.result.connect(lambda data: events.append(("result", data)))
    backend.failed.connect(lambda message: events.append(("failed", message)))
    backend.start()
    deadline = time.monotonic() + 10
    while not any(e[0] in {"result", "failed"} for e in events) and time.monotonic() < deadline:
        QTest.qWait(10)
    backend.cancel()

    assert events == [
        ("progress", "Chargement", 10),
        # The worker echoes the request line it received, byte for byte.
        ("transcript", json.dumps(options) + "\n"),
        ("result", {"cached": True}),
    ]
    assert backend.phase == "load"

import json
import sys
import time

import pytest
from PySide6.QtCore import QProcess
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from src.api import apple_foundation_client as apple
from src.config.settings import Settings
from src.ui.main_window import MainWindow
from src.utils.context_menu import ContextMenuManager


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def wait_until(condition, timeout=3):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert condition()


@pytest.fixture
def helper(monkeypatch, tmp_path, qt_app):
    """Exercise real Qt process I/O with a stand-in for the macOS executable."""
    script = tmp_path / "helper.py"
    started = []

    class Process(QProcess):
        def start(self, program, arguments):
            started.append((program, arguments))
            super().start(sys.executable, [str(script)])

    monkeypatch.setattr(apple, "QProcess", Process)
    monkeypatch.setattr(apple, "preflight_error", lambda: None)

    def configure(source):
        script.write_text(source, encoding="utf-8")
        return started

    return configure


@pytest.mark.parametrize("legacy_custom", [False, True])
def test_provider_migration_and_round_trip(tmp_path, legacy_custom):
    path = str(tmp_path / "settings.ini")
    settings = Settings(path)
    settings.set_use_custom_endpoint(legacy_custom)
    settings.set_api_key("openai-secret")
    settings.set_custom_endpoint("http://localhost:11434")
    settings.set_custom_model("local-model")
    assert settings.get_ai_provider() == ("custom" if legacy_custom else "openai")
    settings.set_ai_provider("apple")
    settings.sync()

    reloaded = Settings(path)
    assert reloaded.get_ai_provider() == "apple"
    assert reloaded.get_reasoning_effort() == "none"
    assert not reloaded.get_use_custom_endpoint()
    assert reloaded.get_api_key() == "openai-secret"
    reloaded.set_ai_provider("custom")
    assert reloaded.get_use_custom_endpoint()
    assert reloaded.get_custom_model() == "local-model"
    assert reloaded.get_custom_endpoint() == "http://localhost:11434"


@pytest.mark.parametrize(
    "system,version,machine,exists,expected",
    [
        ("win32", "", "AMD64", True, "os_unsupported"),
        ("darwin", "15.7", "arm64", True, "os_unsupported"),
        ("darwin", "26.0", "x86_64", True, "device_not_eligible"),
        ("darwin", "26.1", "arm64", False, "helper_missing"),
        ("darwin", "26.1", "arm64", True, None),
    ],
)
def test_preflight(monkeypatch, tmp_path, system, version, machine, exists, expected):
    binary = tmp_path / "helper"
    if exists:
        binary.touch()
    monkeypatch.setattr(apple.sys, "platform", system)
    monkeypatch.setattr(apple.platform, "mac_ver", lambda: (version, (), ""))
    monkeypatch.setattr(apple.platform, "machine", lambda: machine)
    monkeypatch.setattr(apple, "helper_path", lambda: binary)
    assert apple.preflight_error() == expected


def test_native_result_preserves_unicode_request_and_insertion_target(helper):
    started = helper(
        'import json, sys\n'
        'r = json.loads(sys.stdin.buffer.read())\n'
        'assert r == {"action": "generate", "prompt": "Corrige", "content": "Été 🌞"}\n'
        'print(json.dumps({"ok": True, "content": "Texte corrigé 🌞"}))\n'
    )
    client = apple.AppleFoundationClient()
    results, errors, starts = [], [], []
    target = object()
    client.request_started_scoped.connect(lambda *args: starts.append(args))
    client.request_finished_scoped.connect(lambda *args: results.append(args))
    client.request_error_scoped.connect(lambda *args: errors.append(args))
    client.send_request("Corrige", "Été 🌞", True, request_id="one", target=target)
    wait_until(lambda: results or errors)
    assert errors == []
    assert starts == [("one", True)]
    assert results == [("one", "Texte corrigé 🌞", True, target)]
    assert started[0][1] == []  # No user text in the command line.
    assert client._requests == {}
    client.close()


@pytest.mark.parametrize("code", [
    "intelligence_disabled", "model_not_ready", "context_exceeded",
    "unsupported_language", "refusal", "guardrail", "unexpected-secret",
])
def test_native_errors_are_actionable_and_do_not_echo_diagnostics(helper, code):
    helper(
        'import json, sys\njson.load(sys.stdin)\n'
        'print("private selected text", file=sys.stderr)\n'
        f'print({json.dumps(json.dumps({"ok": False, "code": code}))})\n'
    )
    request = apple.FoundationModelsRequest()
    errors, results = [], []
    request.failed.connect(errors.append)
    request.succeeded.connect(results.append)
    request.start({"action": "availability"})
    wait_until(lambda: errors or results)
    assert results == []
    assert errors == [apple.ERROR_MESSAGES.get(code, apple.ERROR_MESSAGES["helper_failed"])]


@pytest.mark.parametrize("output", [
    "invalid JSON private text", "[]", '{"ok": "true"}', '{"ok": false, "code": []}',
])
def test_invalid_native_output_fails_closed(helper, output):
    helper(f'import sys\nsys.stdin.read()\nprint({output!r})\n')
    request = apple.FoundationModelsRequest()
    errors = []
    request.failed.connect(errors.append)
    request.start({"action": "availability"})
    wait_until(lambda: errors)
    assert errors == [apple.ERROR_MESSAGES["helper_failed"]]


def test_timeout_terminates_helper_and_emits_only_one_error(helper):
    helper('import sys, time\nsys.stdin.read()\ntime.sleep(30)\n')
    request = apple.FoundationModelsRequest()
    errors = []
    request.failed.connect(errors.append)
    request.start({"action": "generate"}, timeout_ms=100)
    wait_until(lambda: errors)
    assert errors == [apple.ERROR_MESSAGES["timeout"]]
    assert request._process.state() == QProcess.ProcessState.NotRunning


def test_close_cancels_inflight_generation_without_late_signals(helper):
    helper('import sys, time\nsys.stdin.read()\ntime.sleep(30)\n')
    client = apple.AppleFoundationClient()
    signals = []
    client.request_error_scoped.connect(lambda *args: signals.append(args))
    client.request_finished_scoped.connect(lambda *args: signals.append(args))
    client.send_request("Corrige", "Texte", request_id="one")
    request = client._requests["one"]
    wait_until(lambda: request._process.state() == QProcess.ProcessState.Running)
    client.close()
    assert request._process.state() == QProcess.ProcessState.NotRunning
    QTest.qWait(30)
    assert signals == []
    assert client._requests == {}


def test_unavailable_preflight_emits_error_asynchronously(qt_app, monkeypatch):
    monkeypatch.setattr(apple, "preflight_error", lambda: "helper_missing")
    client = apple.AppleFoundationClient()
    errors = []
    client.request_error_scoped.connect(lambda *args: errors.append(args))
    client.send_request("Corrige", "Texte", request_id="missing")
    wait_until(lambda: errors)
    assert errors == [("missing", apple.ERROR_MESSAGES["helper_missing"])]
    assert client._requests == {}
    client.close()


def test_switching_provider_preserves_inflight_apple_request(helper, tmp_path):
    helper(
        'import json, sys, time\njson.load(sys.stdin)\ntime.sleep(0.1)\n'
        'print(json.dumps({"ok": True, "content": "Completed locally"}))\n'
    )
    settings = Settings(str(tmp_path / "settings.ini"))
    settings.set_ai_provider("apple")
    manager = ContextMenuManager(settings)
    previous = manager.api_client
    results = []
    previous.request_finished_scoped.connect(lambda *args: results.append(args))
    request_id = manager._send_request("Corrige", "Texte")
    settings.set_ai_provider("openai")
    manager.update_client_config()
    assert previous in manager._retired_clients
    wait_until(lambda: results)
    assert results[0][:2] == (request_id, "Completed locally")
    assert previous._closed
    assert manager._pending_requests == {}
    assert previous not in manager._retired_clients
    manager.close()


def test_provider_selection_saves_without_api_key_or_endpoint(qt_app, tmp_path, monkeypatch):
    monkeypatch.setattr(apple, "preflight_error", lambda: "intelligence_disabled")
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
    settings = Settings(str(tmp_path / "settings.ini"))
    manager = ContextMenuManager(settings)
    window = MainWindow(settings, context_menu_manager=manager)
    window.provider_combo.setCurrentIndex(window.provider_combo.findData("apple"))
    wait_until(lambda: window._apple_probe is None)
    assert window.apple_status.text() == apple.ERROR_MESSAGES["intelligence_disabled"]
    assert not window.apple_group.isHidden()
    assert window.openai_group.isHidden() and window.custom_group.isHidden()
    assert window.save_settings()
    assert settings.get_ai_provider() == "apple"
    assert isinstance(manager.api_client, apple.AppleFoundationClient)
    window.provider_combo.setCurrentIndex(window.provider_combo.findData("openai"))
    assert window.save_settings()
    assert not isinstance(manager.api_client, apple.AppleFoundationClient)
    manager.close()
    window._quitting = True
    window.close()

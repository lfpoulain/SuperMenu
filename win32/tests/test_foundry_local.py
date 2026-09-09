import json
import os
import sys
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from src.api import foundry_worker
from src.api.foundry_client import FoundryClient, FoundryService
from src.api.foundry_worker import (
    FoundryRuntime,
    LocalError,
    clean_response,
    configure_text_model,
)
from src.config.settings import Settings
from src.config import settings as settings_module


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module.os.path, "expanduser", lambda _p: str(tmp_path))
    return Settings()


def wait_until(app, predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert predicate()


def test_legacy_provider_migration_and_foundry_persistence(settings):
    settings.settings.remove("ai_provider")
    settings.settings.setValue("use_custom_endpoint", "true")
    assert settings.get_ai_provider() == "custom"
    settings.set_custom_endpoint("http://localhost:11434")
    settings.set_custom_model("existing")
    settings.set_ai_provider("foundry")
    settings.set_foundry_model("qwen3.5-9b")
    settings.sync()
    reloaded = Settings()
    assert reloaded.get_ai_provider() == "foundry"
    assert reloaded.get_foundry_model() == "qwen3.5-9b"
    assert not reloaded.get_use_custom_endpoint()
    assert reloaded.get_reasoning_effort() == "none"
    assert reloaded.get_custom_model() == "existing"
    reloaded.reset_to_defaults()
    assert reloaded.get_ai_provider() == "openai"
    assert reloaded.get_foundry_model() == "qwen3.5-4b"


def test_private_model_configuration_preserves_weights_and_is_idempotent(tmp_path):
    folder = tmp_path / "cache/models/Microsoft/qwen/v3"
    folder.mkdir(parents=True)
    (folder / "inference_model.json").write_text(json.dumps({"Name": "qwen:3"}))
    template = "{% if enable_thinking is defined and enable_thinking is false %}direct{% endif %}"
    (folder / "chat_template.jinja").write_text(template)
    (folder / "genai_config.json").write_text(
        json.dumps({"search": {"max_length": 262144}, "model": {"test": True}})
    )
    weights = folder / "text.onnx"
    weights.write_bytes(b"original-weights")
    configure_text_model(tmp_path, "qwen:3")
    first = (folder / "chat_template.jinja").read_text()
    configure_text_model(tmp_path, "qwen:3")
    assert (folder / "chat_template.jinja").read_text() == first
    assert first.startswith("{%- set enable_thinking = false %}")
    assert "is false" not in first
    assert weights.read_bytes() == b"original-weights"
    config = json.loads((folder / "genai_config.json").read_text())
    assert config == {"search": {"max_length": 32768}, "model": {"test": True}}
    with pytest.raises(LocalError, match="incomplets"):
        configure_text_model(tmp_path, "missing")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Bonjour.", "Bonjour."),
        (
            "Thinking Process: hidden</think>\nLes enfants jouent.",
            "Les enfants jouent.",
        ),
        ("<think>hidden</think>\nHello<|im_end|>", "Hello"),
    ],
)
def test_only_final_text_is_returned(text, expected):
    assert clean_response(text) == expected


@pytest.mark.parametrize("text", ["", "<think>unfinished", "thinking</think>"])
def test_empty_or_unfinished_answers_fail(text):
    with pytest.raises(LocalError):
        clean_response(text)


class FakeModel:
    def __init__(self, alias, cached=True):
        self.alias = alias
        self.id = alias + ":3"
        self.is_cached = cached
        self.loads = self.unloads = 0
        self.requests = []
        self.reason = "stop"
        self.settings = SimpleNamespace()

    def load(self):
        self.loads += 1

    def unload(self):
        self.unloads += 1

    def get_chat_client(self):
        return self

    def complete_chat(self, messages):
        self.requests.append(messages)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason=self.reason,
                    message=SimpleNamespace(content="Résultat"),
                )
            ]
        )


def runtime_with_models(tmp_path, monkeypatch):
    models = {a: FakeModel(a) for a in ("qwen3.5-4b", "qwen3.5-9b")}
    runtime = FoundryRuntime(tmp_path)
    runtime.manager = SimpleNamespace(catalog=SimpleNamespace(get_model=models.get))
    monkeypatch.setattr(foundry_worker, "configure_text_model", lambda *_a: None)
    return runtime, models


def test_generation_reuses_memory_and_unloads_when_switching(tmp_path, monkeypatch):
    runtime, models = runtime_with_models(tmp_path, monkeypatch)
    request = {
        "operation": "generate",
        "model": "qwen3.5-4b",
        "prompt": "Corrige",
        "content": "texte",
    }
    assert runtime.execute(request, lambda _p: None) == {"text": "Résultat"}
    runtime.execute(request, lambda _p: None)
    first = models[request["model"]]
    assert first.loads == 1
    assert first.settings.max_tokens == 2048
    assert first.requests[0][-1]["content"] == "Corrige\n\ntexte"
    request["model"] = "qwen3.5-9b"
    runtime.execute(request, lambda _p: None)
    assert first.unloads == 1
    assert models["qwen3.5-9b"].loads == 1


def test_missing_weights_never_downloads_implicitly_and_truncation_fails(
    tmp_path, monkeypatch
):
    runtime, models = runtime_with_models(tmp_path, monkeypatch)
    model = models["qwen3.5-4b"]
    model.is_cached = False
    request = {
        "operation": "generate",
        "model": model.alias,
        "prompt": "Corrige",
        "content": "Texte",
    }
    with pytest.raises(LocalError, match="Téléchargez"):
        runtime.execute(request, lambda _p: None)
    assert model.loads == 0
    model.is_cached = True
    model.reason = "length"
    with pytest.raises(LocalError, match="interrompue"):
        runtime.execute(request, lambda _p: None)


@pytest.fixture
def service(app, tmp_path):
    worker = tmp_path / "worker.py"
    worker.write_text(
        """import json,sys,time
for line in sys.stdin:
 r=json.loads(line)
 if r.get('content') == 'crash': sys.exit(2)
 if r.get('content') == 'wait': time.sleep(20)
 print(json.dumps({'id':r['id'],'progress':{'percent':50}}),flush=True)
 print(json.dumps({'id':r['id'],'result':{'text':r.get('content','ok')}}),flush=True)
""",
        encoding="utf-8",
    )
    instance = FoundryService(command=(sys.executable, [str(worker)]))
    yield instance
    instance.close()


def test_subprocess_routing_queue_and_client_switch(
    app, settings, service, monkeypatch
):
    monkeypatch.setattr("src.api.foundry_client.platform_error", lambda: "")
    first, second = FoundryClient(settings, service), FoundryClient(settings, service)
    results = []
    first.request_finished_scoped.connect(lambda *args: results.append(args))
    second.request_finished_scoped.connect(lambda *args: results.append(args))
    target = object()
    first.send_request("Corrige", "été", True, request_id="old", target=target)
    second.send_request("Traduis", "summer", request_id="new")
    wait_until(app, lambda: len(results) == 2)
    assert results == [("old", "été", True, target), ("new", "summer", False, None)]
    first.close()
    second.close()


def test_crash_fails_active_request_and_restarts_for_next(app, service):
    errors, results = [], []
    service.failed.connect(lambda *args: errors.append(args))
    service.completed.connect(lambda *args: results.append(args))
    service.submit("generate", request_id="bad", content="crash")
    service.submit("generate", request_id="good", content="ok")
    wait_until(app, lambda: len(results) == 1)
    assert errors[0][0] == "bad"
    assert results == [("good", {"text": "ok"})]


def test_timeout_kills_native_work_and_allows_retry(app, service):
    errors, results = [], []
    service.failed.connect(lambda *args: errors.append(args))
    service.completed.connect(lambda *args: results.append(args))
    service.submit("generate", request_id="slow", content="wait")
    wait_until(app, lambda: service._active is not None)
    service._timer.start(50)
    service.submit("generate", request_id="next", content="ok")
    wait_until(app, lambda: len(results) == 1)
    assert errors[0][0] == "slow"
    assert results[0][0] == "next"


def test_close_cancels_own_request_without_late_insertion(
    app, settings, service, monkeypatch
):
    monkeypatch.setattr("src.api.foundry_client.platform_error", lambda: "")
    client = FoundryClient(settings, service)
    results = []
    client.request_finished_scoped.connect(lambda *args: results.append(args))
    client.send_request("p", "wait", request_id="cancel")
    wait_until(app, lambda: service._active is not None)
    client.close()
    assert service._active is None
    assert not results


@pytest.mark.parametrize("content", ["data:image/png;base64,AAAA", "x" * 16001, None])
def test_invalid_input_never_reaches_native_process(
    app, settings, service, monkeypatch, content
):
    monkeypatch.setattr("src.api.foundry_client.platform_error", lambda: "")
    client = FoundryClient(settings, service)
    errors = []
    client.request_error_scoped.connect(lambda *args: errors.append(args))
    client.send_request("p", content)
    assert len(errors) == 1
    assert not service._queue
    client.close()


def test_foundry_settings_download_progress_and_save_without_key(
    app, settings, monkeypatch
):
    from PySide6.QtCore import QObject, Signal
    from src.ui.main_window import MainWindow
    from src.ui import foundry_settings

    class FakeService(QObject):
        completed = Signal(str, object)
        failed = Signal(str, str)
        progress = Signal(str, object)

        def __init__(self):
            super().__init__()
            self.commands = []

        def submit(self, operation, **payload):
            self.commands.append((operation, payload))
            return str(len(self.commands))

        def cancel(self, _request_id):
            pass

    service = FakeService()
    monkeypatch.setattr(foundry_settings, "get_foundry_service", lambda: service)
    monkeypatch.setattr(foundry_settings, "platform_error", lambda: "")
    monkeypatch.setattr(settings, "get_api_key", lambda: "")
    monkeypatch.setattr(settings, "set_api_key", lambda _key: None)
    monkeypatch.setattr(settings, "get_custom_endpoint_api_key", lambda: "")
    monkeypatch.setattr(settings, "set_custom_endpoint_api_key", lambda _key: None)
    monkeypatch.setattr(
        "src.ui.main_window.QMessageBox.information", lambda *_args: None
    )
    window = MainWindow(settings)
    window.ai_provider_combo.setCurrentIndex(
        window.ai_provider_combo.findData("foundry")
    )
    panel = window.foundry_group
    assert service.commands == [("probe", {})]
    assert not panel.download_button.isEnabled()
    model = {"alias": "qwen3.5-9b", "cached": False, "size_mb": 5569, "device": "CPU"}
    service.completed.emit("1", {"models": [model], "cache_dir": "test-cache"})
    panel.model_combo.setCurrentIndex(panel.model_combo.findData("qwen3.5-9b"))
    assert panel.download_button.isEnabled()
    panel.download_button.click()
    assert service.commands[-1] == ("download", {"model": "qwen3.5-9b"})
    service.progress.emit("2", {"percent": 45})
    assert panel.progress_bar.value() == 45
    service.completed.emit("2", {**model, "cached": True})
    assert not panel.download_button.isEnabled()
    assert "Téléchargé" in panel.model_info.text()
    window.save_api_key()
    assert settings.get_ai_provider() == "foundry"
    assert settings.get_foundry_model() == "qwen3.5-9b"
    assert settings.get_api_key() == ""
    window.hide()
    window.deleteLater()

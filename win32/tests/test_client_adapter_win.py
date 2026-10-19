"""Windows adapter regressions: images stay opt-in, cutoffs never get pasted."""

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from supermenu_core.api import openai_client as client_module
from src.api.openai_client import OpenAIClient


class FakeSettings:
    def __init__(self, provider="openai", endpoint="", model="gpt-5.6-sol"):
        self.provider = provider
        self.endpoint = endpoint
        self.model = model

    def get_use_custom_endpoint(self):
        return self.provider != "openai"

    def get_custom_endpoint(self):
        return self.endpoint

    def get_custom_endpoint_type(self):
        return self.provider

    def get_custom_model(self):
        return self.model

    def get_model(self):
        return self.model

    def get_reasoning_effort(self):
        return "none"


@pytest.fixture(autouse=True)
def isolated_capabilities_cache():
    client_module.clear_capabilities_cache()
    yield
    client_module.clear_capabilities_cache()


def test_windows_adapter_keeps_a_selected_image_path_as_text(tmp_path):
    """Selecting "C:\\...\\scan.png" then "Traduire" must not upload the file."""
    image = tmp_path / "scan_contrat.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nprivate")
    client = OpenAIClient(FakeSettings(), api_key="key")

    data, cleanup_path = client._build_request_data("Traduis", str(image))

    assert client.allow_images is True
    assert cleanup_path is None
    assert data["messages"][0]["content"] == f"Traduis\n\n{image}"
    client.close()


def test_windows_adapter_still_sends_screen_captures():
    client = OpenAIClient(FakeSettings(), api_key="key")

    data, _ = client._build_request_data("Décris", "data:image/png;base64,abc123")

    parts = data["messages"][0]["content"]
    assert parts[1]["image_url"]["url"] == "data:image/png;base64,abc123"
    client.close()


def test_windows_adapter_reports_a_cut_answer_instead_of_pasting_it(monkeypatch):
    client = OpenAIClient(
        FakeSettings("ollama", "http://localhost:11434", "qwen3"),
    )
    monkeypatch.setattr(client, "_ensure_ollama_model_capabilities", lambda: None)
    monkeypatch.setattr(
        client,
        "_perform_request",
        lambda *_a, **_k: SimpleNamespace(
            status_code=200,
            json=lambda: {
                "message": {"thinking": "Je dois d'abord", "content": ""},
                "done_reason": "length",
            },
        ),
    )
    pasted, errors = [], []
    client.request_finished_scoped.connect(lambda *args: pasted.append(args))
    client.request_error_scoped.connect(lambda _rid, message: errors.append(message))

    client._process_request_thread("rid", "Corrige", "Texte", True, False, object())

    assert pasted == []
    assert errors and "interrompu" in errors[0]
    client.close()


def test_windows_adapter_accepts_the_native_lmstudio_api_url():
    client = OpenAIClient(
        FakeSettings("lmstudio", "http://localhost:1234/api/v1", "gemma"),
    )

    assert client.api_url == "http://localhost:1234/api/v1/chat"
    client.close()

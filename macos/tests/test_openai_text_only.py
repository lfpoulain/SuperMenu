"""The macOS adapter of the shared client only ever sends text."""

from types import SimpleNamespace

import pytest

from src.api.openai_client import OpenAIClient
from supermenu_core.api.openai_client import clear_capabilities_cache


@pytest.fixture(autouse=True)
def isolated_capabilities_cache():
    # Probes are shared by every client of the process: a test must neither
    # inherit nor leave behind the capabilities of another test.
    clear_capabilities_cache()
    yield
    clear_capabilities_cache()


class DummySettings:
    def __init__(self, provider="openai"):
        self.provider = provider

    def get_use_custom_endpoint(self):
        return self.provider != "openai"

    def get_custom_endpoint(self):
        return "http://localhost:11434"

    def get_custom_endpoint_type(self):
        return self.provider

    def get_custom_model(self):
        return "local-model"

    def get_model(self):
        return "gpt-5.6-sol"

    def get_reasoning_effort(self):
        return "none"


def test_openai_payload_is_text_only():
    client = OpenAIClient(DummySettings(), api_key="test-key")
    data, cleanup_path = client._build_request_data("Corrige", "Bonjour")
    assert cleanup_path is None
    assert data["messages"] == [
        {"role": "user", "content": "Corrige\n\nBonjour"}
    ]
    assert "image" not in str(data).casefold()


def test_ollama_payload_is_text_only():
    client = OpenAIClient(DummySettings("ollama"), api_key=None)
    data, cleanup_path = client._build_request_data("Résume", "Un texte")
    assert cleanup_path is None
    assert data["messages"][0]["content"] == "Résume\n\nUn texte"
    assert "images" not in data["messages"][0]


def test_lm_studio_payload_is_text_only():
    client = OpenAIClient(DummySettings("lmstudio"), api_key=None)
    data, cleanup_path = client._build_request_data("Explique", "Un texte")
    assert cleanup_path is None
    assert data["input"] == "Explique\n\nUn texte"
    assert isinstance(data["input"], str)


def test_image_like_content_stays_text_on_macos():
    client = OpenAIClient(DummySettings(), api_key="test-key")

    data, cleanup_path = client._build_request_data(
        "Analyse",
        "data:image/png;base64,abc123",
    )

    assert cleanup_path is None
    assert data["messages"][0]["content"] == (
        "Analyse\n\ndata:image/png;base64,abc123"
    )


def test_openai_key_is_never_forwarded_to_custom_endpoint():
    client = OpenAIClient(DummySettings("ollama"), api_key="secret-openai-key")

    assert "Authorization" not in client._build_headers()


def test_openai_key_is_sent_only_to_openai():
    client = OpenAIClient(DummySettings(), api_key="secret-openai-key")

    assert client._build_headers()["Authorization"] == "Bearer secret-openai-key"


# Regressions of the adapter: cutoffs, file paths and the native LM Studio API.


class ServerSettings:
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


def test_text_only_adapter_reports_an_openai_cutoff(monkeypatch):
    client = OpenAIClient(ServerSettings(), api_key="test-key")
    monkeypatch.setattr(
        client,
        "_perform_request",
        lambda *_a, **_k: SimpleNamespace(
            status_code=200,
            json=lambda: {
                "choices": [
                    {"message": {"content": "Texte coupé"}, "finish_reason": "length"}
                ]
            },
        ),
    )
    inserted, errors = [], []
    client.request_finished_scoped.connect(lambda *args: inserted.append(args))
    client.request_error_scoped.connect(lambda _rid, message: errors.append(message))

    client._process_request_thread("rid", "Corrige", "Texte", True, False, None)

    assert inserted == []
    assert errors and "interrompue" in errors[0]
    client.close()


def test_text_only_adapter_never_reads_a_selected_path(tmp_path):
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"jpeg")
    client = OpenAIClient(ServerSettings(), api_key="test-key")

    data, cleanup_path = client._build_request_data("Explique", str(image))

    assert cleanup_path is None
    assert data["messages"][0]["content"] == f"Explique\n\n{image}"
    client.close()


def test_text_only_adapter_accepts_the_native_lmstudio_api_url():
    client = OpenAIClient(
        ServerSettings("lmstudio", "http://localhost:1234/api/v1", "gemma"),
    )

    assert client.api_url == "http://localhost:1234/api/v1/chat"
    client.close()

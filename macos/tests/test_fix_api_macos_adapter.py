"""macOS adapter regressions for the shared provider client."""

from types import SimpleNamespace

import pytest

from supermenu_core.api import openai_client as client_module
from src.api.openai_client import OpenAIClient


class DummySettings:
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


def test_text_only_adapter_reports_an_openai_cutoff(monkeypatch):
    client = OpenAIClient(DummySettings(), api_key="test-key")
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
    client = OpenAIClient(DummySettings(), api_key="test-key")

    data, cleanup_path = client._build_request_data("Explique", str(image))

    assert cleanup_path is None
    assert data["messages"][0]["content"] == f"Explique\n\n{image}"
    client.close()


def test_text_only_adapter_accepts_the_native_lmstudio_api_url():
    client = OpenAIClient(
        DummySettings("lmstudio", "http://localhost:1234/api/v1", "gemma"),
    )

    assert client.api_url == "http://localhost:1234/api/v1/chat"
    client.close()

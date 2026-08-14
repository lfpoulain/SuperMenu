from supermenu_core.api import openai_client as client_module
from supermenu_core.api.openai_client import OpenAIClient


class FakeSettings:
    def __init__(self, provider="openai", model="gpt-5.6-sol"):
        self.provider = provider
        self.model = model

    def get_use_custom_endpoint(self):
        return self.provider != "openai"

    def get_custom_endpoint(self):
        return "http://localhost:11434"

    def get_custom_endpoint_type(self):
        return self.provider

    def get_custom_model(self):
        return self.model if self.provider != "openai" else ""

    def get_model(self):
        return self.model

    def get_reasoning_effort(self):
        return "none"


def test_text_policy_keeps_image_like_content_as_text():
    client = OpenAIClient(FakeSettings(), api_key="secret", allow_images=False)

    data, cleanup_path = client._build_request_data(
        "Analyse",
        "data:image/png;base64,abc123",
    )

    assert cleanup_path is None
    assert data["messages"][0]["content"].endswith("data:image/png;base64,abc123")


def test_image_policy_builds_an_ollama_multimodal_payload():
    client = OpenAIClient(
        FakeSettings(provider="ollama", model="vision-model"),
        allow_images=True,
    )

    data, cleanup_path = client._build_request_data(
        "Analyse",
        "data:image/png;base64,abc123",
    )

    assert cleanup_path is None
    assert data["messages"] == [
        {
            "role": "user",
            "content": "Analyse",
            "images": ["abc123"],
        }
    ]


def test_openai_key_is_not_forwarded_to_a_custom_endpoint():
    client = OpenAIClient(
        FakeSettings(provider="ollama", model="qwen3"),
        api_key="openai-secret",
    )

    assert "Authorization" not in client._build_headers()


def test_explicit_custom_endpoint_key_is_forwarded_only_to_custom_endpoint():
    client = OpenAIClient(
        FakeSettings(provider="ollama", model="qwen3"),
        api_key="openai-secret",
        endpoint_api_key="local-secret",
    )

    assert client._build_headers()["Authorization"] == "Bearer local-secret"


def test_model_catalog_uses_the_explicit_custom_endpoint_key(monkeypatch):
    captured = {}

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"models": [{"name": "qwen3"}]}

    def fake_get(url, headers, timeout):
        captured.update(url=url, headers=headers, timeout=timeout)
        return Response()

    # Requests go through one pooled session so connections are reused.
    monkeypatch.setattr(client_module._SESSION, "get", fake_get)

    success, models = OpenAIClient.fetch_available_models(
        "https://models.example.test",
        api_key="endpoint-secret",
        endpoint_type="ollama",
    )

    assert success is True
    assert models == ["qwen3"]
    assert captured["headers"]["Authorization"] == "Bearer endpoint-secret"


def test_changing_local_model_invalidates_provider_capabilities():
    client = OpenAIClient(
        FakeSettings(provider="ollama", model="qwen3"),
    )
    client._ollama_capabilities_checked = True
    client._ollama_capabilities = {"thinking"}

    client.set_model("gemma3")

    assert client.model == "gemma3"
    assert client._ollama_capabilities_checked is False
    assert client._ollama_capabilities is None


def test_close_blocks_already_queued_signal_forwarding():
    client = OpenAIClient(FakeSettings(), api_key="secret")
    emitted = []
    client.request_finished.connect(emitted.append)

    client.close()
    client._emit_finished("request", "late result", False, None)

    assert emitted == []

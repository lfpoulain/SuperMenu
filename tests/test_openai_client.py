import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.api.openai_client import OpenAIClient


class FakeSettings:
    def __init__(
        self,
        *,
        use_custom_endpoint=False,
        endpoint_type="ollama",
        custom_endpoint="http://localhost:11434",
        custom_model="qwen3",
        model="gpt-5.2",
        reasoning_effort="none",
    ):
        self.use_custom_endpoint = use_custom_endpoint
        self.endpoint_type = endpoint_type
        self.custom_endpoint = custom_endpoint
        self.custom_model = custom_model
        self.model = model
        self.reasoning_effort = reasoning_effort

    def get_use_custom_endpoint(self):
        return self.use_custom_endpoint

    def get_custom_endpoint(self):
        return self.custom_endpoint

    def get_custom_endpoint_type(self):
        return self.endpoint_type

    def get_custom_model(self):
        return self.custom_model

    def get_model(self):
        return self.model

    def get_reasoning_effort(self):
        return self.reasoning_effort


def test_ollama_chat_payload_uses_native_think_and_non_streaming():
    settings = FakeSettings(use_custom_endpoint=True, custom_model="qwen3", reasoning_effort="high")
    client = OpenAIClient(settings)

    data, image_path = client._build_request_data("Explique", "le sujet")

    assert image_path is None
    assert client.api_url == "http://localhost:11434/api/chat"
    assert data["stream"] is False
    assert data["think"] is True
    assert data["options"]["num_predict"] > 0
    assert data["messages"] == [{"role": "user", "content": "Explique\n\nle sujet"}]


def test_ollama_gpt_oss_uses_string_think_effort():
    settings = FakeSettings(use_custom_endpoint=True, custom_model="gpt-oss:20b", reasoning_effort="medium")
    client = OpenAIClient(settings)

    data, _ = client._build_request_data("Question", "")

    assert data["think"] == "medium"


def test_ollama_image_payload_uses_images_array_not_openai_content_parts():
    settings = FakeSettings(use_custom_endpoint=True, custom_model="qwen3-vl:8b", reasoning_effort="low")
    client = OpenAIClient(settings)

    data, _ = client._build_request_data("Decris", "data:image/png;base64,abc123")

    message = data["messages"][0]
    assert message["content"] == "Decris"
    assert message["images"] == ["abc123"]
    assert not isinstance(message["content"], list)


def test_extract_response_text_can_hide_reasoning_for_direct_insert():
    settings = FakeSettings(use_custom_endpoint=True, custom_model="qwen3", reasoning_effort="low")
    client = OpenAIClient(settings)
    response = {"message": {"thinking": "calcul interne", "content": "reponse finale"}}

    assert client._extract_response_text(response, include_reasoning=True) == (
        "<think>calcul interne</think>\n\nreponse finale"
    )
    assert client._extract_response_text(response, include_reasoning=False) == "reponse finale"


def test_lmstudio_reasoning_payload_uses_reasoning_object():
    settings = FakeSettings(
        use_custom_endpoint=True,
        endpoint_type="lmstudio",
        custom_endpoint="http://localhost:1234",
        custom_model="local-reasoning-model",
        reasoning_effort="high",
    )
    client = OpenAIClient(settings)

    data, _ = client._build_request_data("Question", "")

    assert client.api_url == "http://localhost:1234/v1/chat/completions"
    assert data["reasoning"] == {"effort": "high"}
    assert data["max_tokens"] > 0


def test_model_list_base_url_accepts_chat_endpoint_paths():
    assert OpenAIClient._models_base_url("http://localhost:11434/api/chat", True) == "http://localhost:11434"
    assert OpenAIClient._models_base_url("http://localhost:1234/v1/chat/completions", False) == (
        "http://localhost:1234"
    )

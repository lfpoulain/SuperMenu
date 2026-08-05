import os
import json

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from src.api.openai_client import OpenAIClient


class FakeSettings:
    def __init__(
        self,
        *,
        use_custom_endpoint=False,
        endpoint_type="ollama",
        custom_endpoint="http://localhost:11434",
        custom_model="qwen3",
        model="gpt-5.6-sol",
        reasoning_effort="medium",
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


@pytest.mark.parametrize(
    ("model", "configured_effort", "expected_effort"),
    [
        ("gpt-5.6-sol", "max", "max"),
        ("gpt-5.6-terra", "low", "low"),
        ("gpt-5.6-luna", "none", "none"),
        ("gpt-5.4", "max", "xhigh"),
    ],
)
def test_openai_payload_uses_explicit_model_capabilities(
    model,
    configured_effort,
    expected_effort,
):
    settings = FakeSettings(
        model=model,
        reasoning_effort=configured_effort,
    )
    client = OpenAIClient(settings, api_key="key")

    data, image_path = client._build_request_data("Explique", "le sujet")

    assert image_path is None
    assert client.api_url == "https://api.openai.com/v1/chat/completions"
    assert data["model"] == model
    assert data["reasoning_effort"] == expected_effort
    assert data["max_completion_tokens"] > 0
    assert "max_tokens" not in data


def test_explicit_legacy_openai_model_is_migrated_before_request():
    client = OpenAIClient(
        FakeSettings(model="gpt-5.2", reasoning_effort="none"),
        api_key="key",
        model="gpt-5.2",
    )

    data, _ = client._build_request_data("Question", "")

    assert client.model == "gpt-5.6-sol"
    assert data["model"] == "gpt-5.6-sol"
    assert data["reasoning_effort"] == "none"


def test_ollama_chat_payload_uses_native_think_and_non_streaming():
    settings = FakeSettings(use_custom_endpoint=True, custom_model="qwen3", reasoning_effort="high")
    client = OpenAIClient(settings)

    data, image_path = client._build_request_data("Explique", "le sujet")

    assert image_path is None
    assert client.api_url == "http://localhost:11434/api/chat"
    assert data["stream"] is False
    assert data["think"] is True
    assert "options" not in data
    assert data["messages"] == [{"role": "user", "content": "Explique\n\nle sujet"}]


def test_ollama_gpt_oss_uses_string_think_effort():
    settings = FakeSettings(use_custom_endpoint=True, custom_model="gpt-oss:20b", reasoning_effort="medium")
    client = OpenAIClient(settings)

    data, _ = client._build_request_data("Question", "")

    assert data["think"] == "medium"


def test_ollama_gpt_oss_none_uses_low_because_thinking_cannot_be_disabled():
    settings = FakeSettings(
        use_custom_endpoint=True,
        custom_model="gpt-oss:20b",
        reasoning_effort="none",
    )
    client = OpenAIClient(settings)

    data, _ = client._build_request_data("Question", "")

    assert data["think"] == "low"
    assert client._should_include_reasoning_by_default(False) is False


def test_ollama_omits_think_for_model_without_thinking_capability():
    settings = FakeSettings(
        use_custom_endpoint=True,
        custom_model="gemma3:4b",
        reasoning_effort="high",
    )
    client = OpenAIClient(settings)
    client._ollama_capabilities = {"completion", "vision"}

    data, _ = client._build_request_data("Question", "")

    assert "think" not in data


def test_ollama_reads_thinking_capability_from_show_endpoint(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return {"capabilities": ["completion", "thinking"]}

    monkeypatch.setattr(
        "src.api.openai_client.requests.post",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    client = OpenAIClient(
        FakeSettings(
            use_custom_endpoint=True,
            custom_model="qwen3",
            reasoning_effort="high",
        )
    )

    client._ensure_ollama_model_capabilities()

    assert client._ollama_capabilities == {"completion", "thinking"}


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


def test_extract_response_text_strips_inline_think_when_reasoning_hidden():
    settings = FakeSettings(
        use_custom_endpoint=True,
        endpoint_type="lmstudio",
        custom_endpoint="http://localhost:1234",
        custom_model="openai/gpt-oss-20b",
        reasoning_effort="none",
    )
    client = OpenAIClient(settings)
    response = {
        "choices": [
            {
                "message": {
                    "content": "<think>raisonnement interne</think>\n\nreponse finale",
                    "reasoning": "raisonnement structure",
                }
            }
        ]
    }

    assert client._extract_response_text(response, include_reasoning=False) == "reponse finale"
    assert client._should_include_reasoning_by_default(insert_directly=False) is False


def test_custom_reasoning_low_keeps_reasoning_visible_by_default():
    settings = FakeSettings(
        use_custom_endpoint=True,
        endpoint_type="lmstudio",
        custom_endpoint="http://localhost:1234",
        custom_model="openai/gpt-oss-20b",
        reasoning_effort="low",
    )
    client = OpenAIClient(settings)

    assert client._should_include_reasoning_by_default(insert_directly=False) is True


def test_lmstudio_payload_uses_native_chat_without_artificial_output_cap():
    settings = FakeSettings(
        use_custom_endpoint=True,
        endpoint_type="lmstudio",
        custom_endpoint="http://localhost:1234",
        custom_model="local-reasoning-model",
        reasoning_effort="high",
    )
    client = OpenAIClient(settings)

    data, _ = client._build_request_data("Question", "")

    assert client.api_url == "http://localhost:1234/api/v1/chat"
    assert data == {
        "model": "local-reasoning-model",
        "input": "Question",
        "stream": False,
        "store": False,
        "reasoning": "high",
    }


@pytest.mark.parametrize(
    ("effort", "expected"),
    [
        ("none", "off"),
        ("low", "on"),
        ("high", "on"),
    ],
)
def test_lmstudio_reasoning_is_mapped_to_model_capabilities(effort, expected):
    client = OpenAIClient(
        FakeSettings(
            use_custom_endpoint=True,
            endpoint_type="lmstudio",
            custom_endpoint="http://localhost:1234",
            custom_model="gemma-4-12b",
            reasoning_effort=effort,
        )
    )
    client._lmstudio_reasoning_options = {"off", "on"}

    data, _ = client._build_request_data("Question", "")

    assert data["reasoning"] == expected


def test_lmstudio_none_uses_low_when_model_cannot_disable_reasoning():
    client = OpenAIClient(
        FakeSettings(
            use_custom_endpoint=True,
            endpoint_type="lmstudio",
            custom_endpoint="http://localhost:1234",
            custom_model="gpt-oss-20b",
            reasoning_effort="none",
        )
    )
    client._lmstudio_reasoning_options = {"low", "medium", "high"}

    data, _ = client._build_request_data("Question", "")

    assert data["reasoning"] == "low"


def test_lmstudio_native_reasoning_only_response_is_kept_as_final_answer():
    client = OpenAIClient(
        FakeSettings(
            use_custom_endpoint=True,
            endpoint_type="lmstudio",
            custom_endpoint="http://localhost:1234",
            custom_model="gemma-4-12b",
            reasoning_effort="none",
        )
    )
    response = {
        "output": [
            {
                "type": "reasoning",
                "content": "Le résultat utile renvoyé par le modèle.",
            }
        ]
    }

    assert client._extract_response_text(
        response,
        include_reasoning=False,
    ) == "Le résultat utile renvoyé par le modèle."


def test_lmstudio_compatible_reasoning_only_response_is_kept_as_final_answer():
    client = OpenAIClient(
        FakeSettings(
            use_custom_endpoint=True,
            endpoint_type="lmstudio",
            custom_endpoint="http://localhost:1234",
            custom_model="gemma-4-12b",
            reasoning_effort="none",
        )
    )
    response = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "reasoning": "Résultat placé dans le mauvais canal.",
                }
            }
        ]
    }

    assert client._extract_response_text(
        response,
        include_reasoning=False,
    ) == "Résultat placé dans le mauvais canal."


def test_lmstudio_unclosed_inline_think_is_not_lost_when_it_is_only_output():
    client = OpenAIClient(
        FakeSettings(
            use_custom_endpoint=True,
            endpoint_type="lmstudio",
            custom_endpoint="http://localhost:1234",
            custom_model="gemma-4-12b",
            reasoning_effort="none",
        )
    )
    response = {
        "choices": [
            {"message": {"content": "<think>Réponse malgré la balise non fermée"}}
        ]
    }

    assert client._extract_response_text(
        response,
        include_reasoning=False,
    ) == "Réponse malgré la balise non fermée"


def test_lmstudio_explicit_length_finish_is_detected():
    assert OpenAIClient._response_was_truncated(
        {"choices": [{"finish_reason": "length"}]}
    )
    assert not OpenAIClient._response_was_truncated(
        {"choices": [{"finish_reason": "stop"}]}
    )


def test_lmstudio_reads_reasoning_options_from_native_model_catalog(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "models": [
                    {
                        "key": "gemma-4-12b",
                        "capabilities": {
                            "reasoning": {
                                "allowed_options": ["off", "on"],
                                "default": "on",
                            }
                        },
                    }
                ]
            }

    monkeypatch.setattr(
        "src.api.openai_client.requests.get",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    client = OpenAIClient(
        FakeSettings(
            use_custom_endpoint=True,
            endpoint_type="lmstudio",
            custom_endpoint="http://localhost:1234",
            custom_model="gemma-4-12b",
            reasoning_effort="none",
        )
    )

    client._ensure_lmstudio_model_capabilities()

    assert client._lmstudio_reasoning_options == {"off", "on"}


def test_lmstudio_native_404_falls_back_without_output_token_cap(monkeypatch):
    class FakeResponse:
        def __init__(self, status_code):
            self.status_code = status_code
            self.text = ""

    calls = []

    def fake_post(url, headers, data, timeout):
        calls.append((url, json.loads(data)))
        return FakeResponse(404 if len(calls) == 1 else 200)

    monkeypatch.setattr("src.api.openai_client.requests.post", fake_post)
    client = OpenAIClient(
        FakeSettings(
            use_custom_endpoint=True,
            endpoint_type="lmstudio",
            custom_endpoint="http://localhost:1234",
            custom_model="gemma-4-12b",
            reasoning_effort="none",
        )
    )
    native_data, _ = client._build_request_data("Question", "Contexte")

    response = client._perform_request({}, native_data, timeout=10)

    assert response.status_code == 200
    assert calls[0][0] == "http://localhost:1234/api/v1/chat"
    assert calls[1][0] == "http://localhost:1234/v1/chat/completions"
    assert calls[1][1]["max_tokens"] == -1


def test_model_list_base_url_accepts_chat_endpoint_paths():
    assert OpenAIClient._models_base_url("http://localhost:11434/api/chat", True) == "http://localhost:11434"
    assert OpenAIClient._models_base_url("http://localhost:1234/v1/chat/completions", False) == (
        "http://localhost:1234"
    )


def test_fetch_models_detects_ollama_endpoint(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"models": [{"name": "qwen3"}]}

    called_urls = []

    def fake_get(url, headers, timeout):
        called_urls.append(url)
        return FakeResponse()

    monkeypatch.setattr("src.api.openai_client.requests.get", fake_get)
    success, models = OpenAIClient.fetch_available_models("http://localhost:11434", endpoint_type=None)

    assert success is True
    assert models == ["qwen3"]
    assert called_urls == ["http://localhost:11434/api/tags"]

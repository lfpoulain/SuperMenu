"""Anthropic (Claude) as a text engine: catalogue, requests, answers, routing."""

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from supermenu_core.api import openai_client as client_module
from supermenu_core.api.openai_client import OpenAIClient
from supermenu_core.api.providers import anthropic
from supermenu_core.config.anthropic_models import (
    AVAILABLE_ANTHROPIC_MODELS,
    DEFAULT_ANTHROPIC_MODEL,
    AnthropicSettingsMixin,
    get_anthropic_reasoning_efforts,
    normalize_anthropic_model,
    normalize_anthropic_reasoning_effort,
    supports_server_side_fallback,
)
from supermenu_core.config.model_target import (
    ModelTargetSettings,
    normalize_model_target,
)
from supermenu_core.ui.cloud_models import AnthropicSettingsGroup
from supermenu_core.ui.prompt_model import PromptModelChoice


class Memory:
    def __init__(self):
        self.values = {}
        self.writes = 0

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.writes += 1
        self.values[key] = value


class FakeSettings(AnthropicSettingsMixin):
    def __init__(self, provider="anthropic", model=DEFAULT_ANTHROPIC_MODEL, effort=None):
        self.settings = Memory()
        self.provider = provider
        self.anthropic_key = "sk-ant-test-key-0123456789"
        self.settings.values["anthropic_model"] = model
        if effort is not None:
            self.settings.values["anthropic_reasoning_effort"] = effort

    def get_ai_provider(self):
        return self.provider

    def get_anthropic_api_key(self):
        return self.anthropic_key

    def set_anthropic_api_key(self, api_key):
        self.anthropic_key = api_key

    def get_use_custom_endpoint(self):
        return self.provider == "custom"

    def get_custom_endpoint(self):
        return "http://localhost:1234"

    def get_custom_endpoint_type(self):
        return "lmstudio"

    def get_custom_endpoint_api_key(self):
        return "endpoint-secret"

    def get_custom_model(self):
        return "gemma"

    def get_custom_model_target(self):
        return {}

    def get_custom_reasoning_effort(self):
        return "none"

    def get_model(self):
        return "gpt-5.6-sol"

    def get_openai_reasoning_effort(self, model=None):
        return "medium"

    def get_reasoning_effort(self):
        return self.get_anthropic_reasoning_effort()


@pytest.fixture(autouse=True)
def fresh_provider_state():
    client_module.clear_capabilities_cache()
    yield
    client_module.clear_capabilities_cache()


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def _client(settings=None, **kwargs):
    kwargs.setdefault("allow_images", False)
    return OpenAIClient(settings or FakeSettings(), api_key="openai-secret", **kwargs)


def _run(client, monkeypatch, response, insert_directly=True, include_reasoning=False):
    """Run one request synchronously against a canned HTTP response."""
    monkeypatch.setattr(client, "_perform_request", lambda *_a, **_k: response)
    finished, errors = [], []
    client.request_finished_scoped.connect(
        lambda _rid, text, _direct, _target: finished.append(text)
    )
    client.request_error_scoped.connect(lambda _rid, message: errors.append(message))
    client._process_request_thread(
        "rid", "Corrige", "Texte", insert_directly, include_reasoning, None
    )
    return finished, errors


def _ok(payload):
    return SimpleNamespace(status_code=200, json=lambda: payload, text="")


# Catalogue ---------------------------------------------------------------


def test_catalogue_defaults_and_effort_rules():
    assert DEFAULT_ANTHROPIC_MODEL == "claude-opus-5-5"
    assert AVAILABLE_ANTHROPIC_MODELS[0] == DEFAULT_ANTHROPIC_MODEL
    assert normalize_anthropic_model("  Claude-Sonnet-5-5 ") == "claude-sonnet-5-5"
    assert normalize_anthropic_model("claude-2.1") == DEFAULT_ANTHROPIC_MODEL
    assert normalize_anthropic_model(None) == DEFAULT_ANTHROPIC_MODEL
    for model in AVAILABLE_ANTHROPIC_MODELS:
        assert get_anthropic_reasoning_efforts(model) == [
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        ]
        # Claude cannot stop reasoning through the effort: lightest instead.
        assert normalize_anthropic_reasoning_effort(model, "none") == "low"
        assert normalize_anthropic_reasoning_effort(model, "invalide") == "medium"
        assert normalize_anthropic_reasoning_effort(model, " XHIGH ") == "xhigh"
    assert supports_server_side_fallback("claude-opus-5-5")
    # Anthropic offers no server-side fallback for this model.
    assert not supports_server_side_fallback("claude-haiku-5-5")


def test_settings_mixin_reads_without_rewriting():
    settings = FakeSettings(model="claude-3-opus", effort="none")

    assert settings.get_anthropic_model() == DEFAULT_ANTHROPIC_MODEL
    assert settings.get_anthropic_reasoning_effort() == "low"
    assert settings.get_anthropic_reasoning_effort("claude-haiku-5-5") == "low"
    assert settings.settings.writes == 0

    settings.set_anthropic_model("claude-haiku-5-5")
    settings.set_anthropic_reasoning_effort("max")
    assert settings.get_anthropic_model() == "claude-haiku-5-5"
    assert settings.get_anthropic_reasoning_effort() == "max"


# Requests ----------------------------------------------------------------


def test_request_targets_anthropic_with_its_own_key_only():
    client = _client(FakeSettings(effort="high"))

    headers = client._build_headers()
    data, image_path = client._build_request_data("Corrige", "Texte")

    assert client.api_url == "https://api.anthropic.com/v1/messages"
    assert headers == {
        "Content-Type": "application/json",
        "anthropic-version": anthropic.API_VERSION,
        "x-api-key": "sk-ant-test-key-0123456789",
    }
    # Neither the OpenAI key nor the endpoint token ever reaches Anthropic.
    assert "openai-secret" not in str(headers)
    assert "endpoint-secret" not in str(headers)
    assert image_path is None
    assert data == {
        "model": "claude-opus-5-5",
        "max_tokens": anthropic.MAX_TOKENS,
        "messages": [{"role": "user", "content": "Corrige\n\nTexte"}],
        "output_config": {"effort": "high"},
        "thinking": {"type": "adaptive", "display": "summarized"},
        "fallbacks": "default",
    }
    assert anthropic.request_headers(headers, data)["anthropic-beta"] == (
        anthropic.FALLBACK_BETA
    )
    client.close()


def test_openai_requests_never_carry_the_anthropic_key():
    client = _client(FakeSettings(provider="openai"))

    headers = client._build_headers()

    assert client.use_anthropic_api is False
    assert client.anthropic_api_key == ""
    assert headers == {
        "Content-Type": "application/json",
        "Authorization": "Bearer openai-secret",
    }
    client.close()


def test_prompt_without_reasoning_uses_the_lightest_effort_and_no_summary():
    client = _client(FakeSettings(model="claude-haiku-5-5", effort="max"))

    data, _ = client._build_request_data("Corrige", "Texte", reasoning_mode="off")

    assert data["output_config"] == {"effort": "low"}
    assert "thinking" not in data
    # No server-side fallback exists for this model: the option is not sent.
    assert "fallbacks" not in data
    assert anthropic.request_headers({}, data) == {}
    client.close()


def test_screenshot_is_sent_as_a_base64_image_block():
    client = _client(allow_images=True)

    data, _ = client._build_request_data("Décris", "data:image/png;base64,QUJD")

    assert data["messages"][0]["content"] == [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": "QUJD"},
        },
        {"type": "text", "text": "Décris"},
    ]
    client.close()


def test_missing_anthropic_key_is_reported_before_any_request(monkeypatch):
    settings = FakeSettings()
    settings.anthropic_key = ""
    # A configured OpenAI key must not stand in for the Anthropic one.
    client = _client(settings)
    monkeypatch.setattr(
        client, "_process_request_thread", lambda *_a, **_k: pytest.fail("envoyée")
    )
    errors = []
    client.request_error_scoped.connect(lambda _rid, message: errors.append(message))

    client.send_request("Corrige", "Texte")

    assert len(errors) == 1 and "Anthropic" in errors[0]
    client.close()


# Answers -----------------------------------------------------------------


def test_answer_keeps_text_and_shows_the_reasoning_summary_on_demand(monkeypatch):
    payload = {
        "stop_reason": "end_turn",
        "content": [
            {"type": "thinking", "thinking": "Je vérifie l’accord."},
            {"type": "text", "text": "Texte corrigé."},
        ],
    }

    client = _client()
    finished, errors = _run(client, monkeypatch, _ok(payload))
    assert (finished, errors) == (["Texte corrigé."], [])
    client.close()

    client = _client()
    finished, errors = _run(
        client, monkeypatch, _ok(payload), insert_directly=False, include_reasoning=True
    )
    assert errors == []
    assert finished == ["<think>Je vérifie l’accord.</think>\n\nTexte corrigé."]
    client.close()


def test_reasoning_summary_alone_is_never_promoted_to_an_answer(monkeypatch):
    client = _client()
    finished, errors = _run(
        client,
        monkeypatch,
        _ok(
            {
                "stop_reason": "end_turn",
                "content": [{"type": "thinking", "thinking": "Brouillon interne"}],
            }
        ),
        insert_directly=False,
        include_reasoning=True,
    )

    assert finished == []
    assert len(errors) == 1 and "vide" in errors[0]
    client.close()


def test_refusal_is_an_error_even_with_partial_text(monkeypatch):
    client = _client()
    finished, errors = _run(
        client,
        monkeypatch,
        _ok(
            {
                "stop_reason": "refusal",
                "stop_details": {"type": "refusal", "category": "cyber"},
                "content": [{"type": "text", "text": "Début de rép"}],
            }
        ),
    )

    assert finished == []
    assert len(errors) == 1
    assert "refusé" in errors[0] and "cybersécurité" in errors[0]
    client.close()


def test_refusal_without_details_is_still_reported(monkeypatch):
    client = _client()
    finished, errors = _run(
        client,
        monkeypatch,
        _ok({"stop_reason": "refusal", "stop_details": None, "content": []}),
    )

    assert finished == []
    assert len(errors) == 1 and "refusé" in errors[0]
    client.close()


def test_max_tokens_cutoff_is_an_error_not_an_insertion(monkeypatch):
    client = _client()
    finished, errors = _run(
        client,
        monkeypatch,
        _ok(
            {
                "stop_reason": "max_tokens",
                "content": [{"type": "text", "text": "Texte coupé au mil"}],
            }
        ),
    )

    assert finished == []
    assert len(errors) == 1 and "Claude a interrompu" in errors[0]
    client.close()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "clé API"),
        (404, "pas disponible"),
        (429, "Limite de débit"),
        (529, "surchargé"),
        (418, "Erreur 418"),
    ],
)
def test_http_errors_are_explained_with_the_api_detail(monkeypatch, status, expected):
    client = _client()
    body = '{"type": "error", "error": {"type": "x", "message": "détail serveur"}}'
    finished, errors = _run(
        client,
        monkeypatch,
        SimpleNamespace(status_code=status, text=body, json=lambda: {}),
    )

    assert finished == []
    assert len(errors) == 1
    assert expected in errors[0] and "détail serveur" in errors[0]
    # The raw JSON envelope is not shown to the user.
    assert '"type"' not in errors[0]
    client.close()


# Fallback option ---------------------------------------------------------


def test_rejected_fallback_option_is_retried_once_then_skipped(monkeypatch):
    client = _client()
    calls = []

    def fake_post(headers, data, timeout=60, api_url=None):
        calls.append((dict(headers), dict(data)))
        if "fallbacks" in data:
            return SimpleNamespace(
                status_code=400,
                text="Unexpected value(s) `x` for the `anthropic-beta` header.",
            )
        return SimpleNamespace(status_code=200, text="")

    monkeypatch.setattr(client, "_make_request_with_retry", fake_post)
    headers = client._build_headers()
    data, _ = client._build_request_data("Corrige", "Texte")

    response = client._perform_request(headers, data, timeout=5)

    assert response.status_code == 200
    assert len(calls) == 2
    assert calls[0][0]["anthropic-beta"] == anthropic.FALLBACK_BETA
    assert "fallbacks" in calls[0][1]
    assert "anthropic-beta" not in calls[1][0]
    assert "fallbacks" not in calls[1][1]
    # The same request, minus the option.
    assert {**calls[1][1], "fallbacks": "default"} == calls[0][1]

    # Later requests of this session no longer pay the extra round trip...
    later, _ = client._build_request_data("Corrige", "Texte")
    assert "fallbacks" not in later
    # ...until the configuration changes (another key may accept it).
    client_module.clear_capabilities_cache()
    again, _ = client._build_request_data("Corrige", "Texte")
    assert again["fallbacks"] == "default"
    client.close()


def test_other_bad_requests_are_not_retried(monkeypatch):
    client = _client()
    calls = []

    def fake_post(headers, data, timeout=60, api_url=None):
        calls.append(data)
        return SimpleNamespace(status_code=400, text="max_tokens: too large")

    monkeypatch.setattr(client, "_make_request_with_retry", fake_post)
    data, _ = client._build_request_data("Corrige", "Texte")

    response = client._perform_request(client._build_headers(), data, timeout=5)

    assert response.status_code == 400
    assert len(calls) == 1
    client.close()


# Per-prompt routing ------------------------------------------------------


def test_prompt_target_routes_one_prompt_to_claude():
    base = FakeSettings(provider="openai", effort="high")
    target = normalize_model_target(
        {"provider": "anthropic", "model": "claude-haiku-5-5"}
    )

    view = ModelTargetSettings(base, target)
    client = OpenAIClient(view, api_key="openai-secret", allow_images=False)
    data, _ = client._build_request_data("Corrige", "Texte")

    assert view.get_use_custom_endpoint() is False
    assert view.get_reasoning_effort() == "high"
    assert client.use_anthropic_api is True
    assert client.model == "claude-haiku-5-5"
    assert data["model"] == "claude-haiku-5-5"
    assert data["output_config"] == {"effort": "high"}
    # The general settings are untouched by this prompt's choice.
    assert base.get_anthropic_model() == DEFAULT_ANTHROPIC_MODEL
    assert base.settings.writes == 0
    client.close()


def test_prompt_target_refuses_a_claude_model_this_version_does_not_offer():
    with pytest.raises(ValueError, match="Claude"):
        ModelTargetSettings(
            FakeSettings(), {"provider": "anthropic", "model": "claude-inconnu"}
        )


# Settings widgets --------------------------------------------------------


def test_settings_group_saves_key_model_and_effort(qt_app):
    settings = FakeSettings(effort="low")
    group = AnthropicSettingsGroup(settings)

    assert group.selected_model() == DEFAULT_ANTHROPIC_MODEL
    assert group.selected_effort() == "low"
    assert group.api_key() == "sk-ant-test-key-0123456789"
    assert group.model_hint.text()

    group.model_combo.setCurrentIndex(group.model_combo.findData("claude-sonnet-5-5"))
    group.reasoning_combo.setCurrentText("xhigh")
    group.api_key_input.setText("  sk-ant-autre-cle-0123456789  ")
    assert group.validation_error() == ""
    group.save()

    assert settings.get_anthropic_api_key() == "sk-ant-autre-cle-0123456789"
    assert settings.get_anthropic_model() == "claude-sonnet-5-5"
    assert settings.get_anthropic_reasoning_effort() == "xhigh"

    group.api_key_input.setText("sk-ant court")
    assert "incomplète" in group.validation_error()
    # An empty key can be saved: the request explains what is missing.
    group.api_key_input.setText("")
    assert group.validation_error() == ""

    settings.set_anthropic_model("claude-haiku-5-5")
    group.reload()
    assert group.selected_model() == "claude-haiku-5-5"
    group.deleteLater()


def test_prompt_picker_offers_claude_models(qt_app):
    settings = FakeSettings(provider="openai")
    choice = PromptModelChoice(settings)

    choice.provider.setCurrentIndex(choice.provider.findData("anthropic"))
    # Starts on the model of the general settings.
    assert choice.target() == {
        "provider": "anthropic",
        "model": DEFAULT_ANTHROPIC_MODEL,
    }
    choice.model.setCurrentIndex(choice.model.findData("claude-fable-5-2"))
    assert choice.target() == {"provider": "anthropic", "model": "claude-fable-5-2"}
    assert choice.is_valid()

    choice.set_target({"provider": "anthropic", "model": "claude-sonnet-5-5"})
    assert choice.provider.currentData() == "anthropic"
    assert choice.target()["model"] == "claude-sonnet-5-5"

    # A model this version no longer lists is shown as stored, not replaced.
    choice.set_target({"provider": "anthropic", "model": "claude-ancien"})
    assert choice.target() == {"provider": "anthropic", "model": "claude-ancien"}
    choice.deleteLater()

"""Regressions for the shared provider client (truncation, routing, probes)."""

import threading
from types import SimpleNamespace

import pytest
import requests

from supermenu_core.api import openai_client as client_module
from supermenu_core.api.openai_client import OpenAIClient


class FakeSettings:
    def __init__(
        self,
        provider="openai",
        model="gpt-5.6-sol",
        endpoint="http://localhost:11434",
        effort="none",
    ):
        self.provider = provider
        self.model = model
        self.endpoint = endpoint
        self.effort = effort

    def get_use_custom_endpoint(self):
        return self.provider != "openai"

    def get_custom_endpoint(self):
        return self.endpoint

    def get_custom_endpoint_type(self):
        return self.provider

    def get_custom_model(self):
        return self.model if self.provider != "openai" else ""

    def get_model(self):
        return self.model

    def get_reasoning_effort(self):
        return self.effort


@pytest.fixture(autouse=True)
def isolated_capabilities_cache():
    client_module.clear_capabilities_cache()
    yield
    client_module.clear_capabilities_cache()


def _client(*args, **kwargs):
    kwargs.setdefault("allow_images", False)
    return OpenAIClient(FakeSettings(*args), api_key="test", **kwargs)


def _run(client, monkeypatch, payload, insert_directly=True, include_reasoning=False):
    """Run one request synchronously against a canned provider payload."""
    monkeypatch.setattr(client, "_ensure_ollama_model_capabilities", lambda: None)
    monkeypatch.setattr(client, "_ensure_lmstudio_model_capabilities", lambda: None)
    monkeypatch.setattr(
        client,
        "_perform_request",
        lambda *_a, **_k: SimpleNamespace(status_code=200, json=lambda: payload),
    )
    finished, errors = [], []
    client.request_finished_scoped.connect(
        lambda _rid, text, _direct, _target: finished.append(text)
    )
    client.request_error_scoped.connect(lambda _rid, message: errors.append(message))
    client._process_request_thread(
        "rid", "Corrige", "Texte", insert_directly, include_reasoning, None
    )
    return finished, errors


# Finding 1 -- cutoffs are detected for every provider, before any insertion.

def test_openai_length_cutoff_is_an_error_not_an_insertion(monkeypatch):
    client = _client()
    finished, errors = _run(
        client,
        monkeypatch,
        {"choices": [{"message": {"content": "Texte tronqué au mil"}, "finish_reason": "length"}]},
    )

    assert finished == []
    assert len(errors) == 1 and "interrompue" in errors[0]
    client.close()


def test_ollama_cutoff_does_not_promote_a_partial_trace(monkeypatch):
    client = _client("ollama", "qwen3")
    finished, errors = _run(
        client,
        monkeypatch,
        {
            "message": {"thinking": "Je dois d'abord", "content": ""},
            "done": True,
            "done_reason": "length",
        },
    )

    assert finished == []
    assert len(errors) == 1 and "Ollama" in errors[0]
    client.close()


def test_custom_endpoint_cutoff_is_detected(monkeypatch):
    client = _client("custom", "qwen3", "http://localhost:8000/v1")
    finished, errors = _run(
        client,
        monkeypatch,
        {"choices": [{"message": {"content": "Début"}, "finish_reason": "length"}]},
    )

    assert finished == [] and errors
    client.close()


def test_generic_server_cutoff_names_supermenu_cap_and_reasoning(monkeypatch):
    """A reasoning trace can spend SuperMenu's whole cap on a generic server."""
    client = _client("custom", "qwen3-thinking", "http://localhost:8000/v1")
    finished, errors = _run(
        client,
        monkeypatch,
        {
            "choices": [
                {
                    "message": {"content": "", "reasoning_content": "Je réfléchis…"},
                    "finish_reason": "length",
                }
            ]
        },
    )

    assert finished == []
    assert len(errors) == 1
    assert f"{client_module.DEFAULT_MAX_TOKENS} tokens" in errors[0]
    assert "SuperMenu" in errors[0] and "raisonnement" in errors[0]
    client.close()


def test_complete_answers_and_reasoning_only_answers_still_succeed(monkeypatch):
    client = _client("ollama", "qwen3")
    finished, errors = _run(
        client,
        monkeypatch,
        {
            "message": {"thinking": "Réponse utile", "content": ""},
            "done": True,
            "done_reason": "stop",
        },
    )

    assert errors == []
    assert finished == ["Réponse utile"]
    client.close()


def test_responses_style_incomplete_status_is_a_cutoff():
    assert OpenAIClient._response_was_truncated(
        {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}
    )
    assert not OpenAIClient._response_was_truncated({"done_reason": "stop"})
    assert not OpenAIClient._response_was_truncated(
        {"choices": [{"finish_reason": "content_filter"}]}
    )


def test_openai_budget_leaves_room_for_reasoning_but_custom_cap_is_unchanged():
    openai_data, _ = _client("openai", "gpt-5.6-sol", "", "medium")._build_request_data(
        "Corrige", "Texte"
    )
    custom_data, _ = _client("custom", "local", "http://localhost:8000/v1")._build_request_data(
        "Corrige", "Texte"
    )

    assert openai_data["max_completion_tokens"] == client_module.OPENAI_MAX_COMPLETION_TOKENS
    assert openai_data["max_completion_tokens"] > 2048
    assert custom_data["max_tokens"] == client_module.DEFAULT_MAX_TOKENS == 2048


# Finding 17 -- the native LM Studio API URL keeps its server root.

@pytest.mark.parametrize(
    "endpoint",
    [
        "http://localhost:1234",
        "http://localhost:1234/",
        "http://localhost:1234/v1",
        "http://localhost:1234/v1/chat/completions",
        "http://localhost:1234/api/v1",
        "http://localhost:1234/api/v1/",
        "http://localhost:1234/api/v1/chat",
        "http://localhost:1234/api/v1/models",
    ],
)
def test_lmstudio_endpoint_forms_share_one_server_root(endpoint):
    client = _client("lmstudio", "gemma", endpoint)

    assert client.api_url == "http://localhost:1234/api/v1/chat"
    assert client._lmstudio_compat_url == "http://localhost:1234/v1/chat/completions"
    assert OpenAIClient._models_base_url(endpoint, False, lmstudio=True) == (
        "http://localhost:1234"
    )
    client.close()


def test_generic_servers_under_api_v1_keep_their_previous_root():
    # Only LM Studio's native API lives at "<root>/api/v1"; a generic
    # OpenAI-compatible router there still lists ".../api" + "/v1/models".
    assert OpenAIClient._models_base_url(
        "https://router.example.test/api/v1", False
    ) == "https://router.example.test/api"


def test_lmstudio_catalog_from_native_api_url_uses_the_server_root(monkeypatch):
    from supermenu_core.api import lmstudio_provenance

    urls = []

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"models": [{"key": "qwen"}]}

    def fake_get(url, headers, timeout):
        urls.append(url)
        return Response()

    bases = []
    monkeypatch.setattr(client_module._SESSION, "get", fake_get)
    monkeypatch.setattr(
        lmstudio_provenance,
        "fetch_provenance",
        lambda base, *_a, **_k: bases.append(base) or ([], []),
    )

    success, _models = OpenAIClient.fetch_available_model_details(
        "http://localhost:1234/api/v1", endpoint_type="lmstudio"
    )

    assert success
    assert urls == ["http://localhost:1234/api/v1/models"]
    assert bases == ["http://localhost:1234"]


# Finding 19 -- an orphan closing tag no longer leaks the reasoning.

def test_orphan_closing_tag_hides_the_reasoning_from_direct_insertion():
    client = _client("custom", "qwen3-thinking", "http://localhost:8000/v1")
    response = {
        "choices": [
            {
                "message": {
                    "content": "L'utilisateur veut une correction…\n</think>\n\nBonjour !"
                },
                "finish_reason": "stop",
            }
        ]
    }

    assert client._extract_response_text(response, include_reasoning=False) == "Bonjour !"
    assert client._extract_response_text(response, include_reasoning=True) == (
        "<think>L'utilisateur veut une correction…</think>\n\nBonjour !"
    )
    client.close()


def test_closing_tag_quoted_in_code_is_inserted_whole():
    """Only a tag that opens or ends its line closes an injected reasoning."""
    code = 'THINK_CLOSE = re.compile(r"</think>")  # ferme le bloc\nprint("ok")'
    client = _client("ollama", "qwen3")
    response = {"message": {"content": code}, "done": True, "done_reason": "stop"}

    assert client._extract_response_text(response, include_reasoning=False) == code
    client.close()


# Finding 20 -- a failed probe is retried instead of being trusted forever.

def test_failed_ollama_probe_is_retried_after_the_backoff(monkeypatch):
    calls = []
    outcomes = [requests.exceptions.ConnectionError("refused")]

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"capabilities": ["completion"]}

    def fake_post(url, **_kwargs):
        calls.append(url)
        if outcomes:
            raise outcomes.pop(0)
        return Response()

    monkeypatch.setattr(client_module._SESSION, "post", fake_post)
    client = _client("ollama", "gemma3", "http://probe-retry.test:11434", "medium")

    client._ensure_ollama_model_capabilities()
    assert client._ollama_capabilities_checked is False
    assert client._build_request_data("Question", "")[0]["think"] is True

    client._ensure_ollama_model_capabilities()
    assert len(calls) == 1, "the backoff avoids a probe on every request"

    client._ollama_probe_failed_at -= client_module.CAPABILITIES_RETRY_DELAY + 1
    client._ensure_ollama_model_capabilities()

    assert len(calls) == 2
    assert client._ollama_capabilities == {"completion"}
    assert "think" not in client._build_request_data("Question", "")[0]
    client.close()


def test_failed_lmstudio_probe_is_retried_after_the_backoff(monkeypatch):
    calls = []

    class Response:
        def __init__(self, status_code):
            self.status_code = status_code

        @staticmethod
        def json():
            return {
                "models": [
                    {
                        "key": "gemma",
                        "capabilities": {
                            "reasoning": {"allowed_options": ["off", "on"], "default": "on"}
                        },
                    }
                ]
            }

    def fake_get(url, **_kwargs):
        calls.append(url)
        return Response(503 if len(calls) == 1 else 200)

    monkeypatch.setattr(client_module._SESSION, "get", fake_get)
    client = _client("lmstudio", "gemma", "http://probe-retry.test:1234")

    client._ensure_lmstudio_model_capabilities()
    assert client._lmstudio_catalog_checked is False

    client._lmstudio_probe_failed_at -= client_module.CAPABILITIES_RETRY_DELAY + 1
    client._ensure_lmstudio_model_capabilities()

    assert len(calls) == 2
    assert client._lmstudio_reasoning_options == ["off", "on"]
    client.close()


def test_ollama_thinking_refusal_is_retried_once_without_think(monkeypatch):
    client = _client("ollama", "gemma3", "http://localhost:11434", "medium")
    sent = []

    def request(_headers, data, **_options):
        sent.append(dict(data))
        if len(sent) == 1:
            return SimpleNamespace(
                status_code=400,
                text='{"error":"\\"gemma3\\" does not support thinking"}',
            )
        return SimpleNamespace(status_code=200, text="")

    monkeypatch.setattr(client, "_make_request_with_retry", request)
    data, _ = client._build_request_data("Question", "")

    response = client._perform_request({}, data, 60)

    assert response.status_code == 200
    assert sent[0]["think"] is True
    assert "think" not in sent[1]
    client.close()


def test_unrelated_ollama_400_is_not_resent(monkeypatch):
    client = _client("ollama", "gemma3", "http://localhost:11434", "medium")
    sent = []

    def request(_headers, data, **_options):
        sent.append(data)
        return SimpleNamespace(status_code=400, text='{"error":"invalid model name"}')

    monkeypatch.setattr(client, "_make_request_with_retry", request)
    data, _ = client._build_request_data("Question", "")

    assert client._perform_request({}, data, 60).status_code == 400
    assert len(sent) == 1
    client.close()


# Finding 51 -- per-prompt clients reuse a recent probe.

def test_per_prompt_clients_share_a_recent_capability_probe(monkeypatch):
    calls = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"capabilities": ["completion", "thinking"]}

    monkeypatch.setattr(
        client_module._SESSION,
        "post",
        lambda url, **_kwargs: calls.append(url) or Response(),
    )

    first = _client("ollama", "qwen3", "http://shared-cache.test:11434")
    second = _client("ollama", "qwen3", "http://shared-cache.test:11434")
    other_model = _client("ollama", "gemma3", "http://shared-cache.test:11434")
    for client in (first, second, other_model):
        client._ensure_ollama_model_capabilities()

    assert len(calls) == 2
    assert second._ollama_capabilities == {"completion", "thinking"}
    for client in (first, second, other_model):
        client.close()


def test_shared_capabilities_expire(monkeypatch):
    key = ("ollama", "http://expired.test:11434", "qwen3")
    client_module._remember_capabilities(key, frozenset({"thinking"}))
    now = client_module.time.monotonic()
    monkeypatch.setattr(
        client_module.time,
        "monotonic",
        lambda: now + client_module.CAPABILITIES_CACHE_TTL + 1,
    )

    assert client_module._cached_capabilities(key) is None


# Finding 44 -- visibility follows the effort actually sent for the prompt.

@pytest.mark.parametrize(
    ("global_effort", "mode", "expected"),
    [
        ("none", "on", True),
        ("none", "default", False),
        ("low", "off", False),
        ("low", "default", True),
    ],
)
def test_reasoning_visibility_follows_the_prompt_mode(monkeypatch, global_effort, mode, expected):
    captured = []

    class DeferredThread:
        def __init__(self, target, args, daemon):
            captured.append(args)

        def start(self):
            pass

    monkeypatch.setattr(threading, "Thread", DeferredThread)
    client = _client("ollama", "qwen3", "http://localhost:11434", global_effort)

    client.send_request("Analyse", "Texte", reasoning_mode=mode)

    include_reasoning = captured[0][4]
    assert include_reasoning is expected
    client.close()


# Findings 76 / 99 -- a selected file path is never read as an image.

def test_selected_image_path_stays_text(tmp_path):
    image = tmp_path / "scan_contrat.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nprivate")
    client = _client(allow_images=True)

    data, cleanup_path = client._build_request_data("Traduis", str(image))

    assert cleanup_path is None
    assert data["messages"] == [
        {"role": "user", "content": f"Traduis\n\n{image}"}
    ]
    assert image.exists()
    client.close()


def test_unc_and_invalid_paths_are_never_touched(monkeypatch):
    touched = []
    monkeypatch.setattr(
        client_module.os.path,
        "isfile",
        lambda path: touched.append(path) or False,
    )
    client = _client(allow_images=True)

    for content in (r"\\hote\partage\scan.png", "bad\x00name.png", "a" * 5000 + ".jpg"):
        data, cleanup_path = client._build_request_data("Explique", content)
        assert cleanup_path is None
        assert data["messages"][0]["content"].endswith(content)

    assert touched == []
    client.close()


def test_owned_screenshot_fallback_is_still_sent_as_image(monkeypatch, tmp_path):
    monkeypatch.setattr(client_module.tempfile, "gettempdir", lambda: str(tmp_path))
    screenshot = tmp_path / "supermenu_screenshot_42.png"
    screenshot.write_bytes(b"png-bytes")
    client = _client(allow_images=True)

    data, cleanup_path = client._build_request_data("Décris", str(screenshot))

    assert cleanup_path == str(screenshot)
    content = data["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "Décris"}
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    client._cleanup_owned_image(cleanup_path)
    assert not screenshot.exists()
    client.close()


# Finding 77 -- a read timeout is not resent; connection failures still are.

def test_read_timeout_is_not_resent(monkeypatch):
    calls = []

    def fake_post(url, headers, data, timeout):
        calls.append(timeout)
        raise requests.exceptions.ReadTimeout("slow generation")

    monkeypatch.setattr(client_module._SESSION, "post", fake_post)
    client = OpenAIClient(FakeSettings(), api_key="test", retry_delay=0)

    with pytest.raises(Exception, match="délai prévu"):
        client._make_request_with_retry({}, {"model": "x"}, timeout=180)

    assert calls == [(client_module.CONNECT_TIMEOUT, 180)]
    client.close()


@pytest.mark.parametrize(
    "failure",
    [requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError],
)
def test_connection_failures_are_still_retried(monkeypatch, failure):
    calls = []

    def fake_post(url, headers, data, timeout):
        calls.append(url)
        if len(calls) < 3:
            raise failure("offline")
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(client_module._SESSION, "post", fake_post)
    client = OpenAIClient(FakeSettings(), api_key="test", retry_delay=0)

    assert client._make_request_with_retry({}, {"model": "x"}, timeout=60).status_code == 200
    assert len(calls) == 3
    client.close()


# Finding 79 -- the legacy synchronous API follows the same rules.

def test_legacy_sync_request_refuses_an_incomplete_custom_configuration():
    client = _client("ollama", "", "http://localhost:11434")

    with pytest.raises(Exception, match="incomplète"):
        client.send_request_sync("Corrige", "Texte")
    client.close()


def test_legacy_sync_request_detects_cutoffs_and_formats_errors_once(monkeypatch):
    client = _client()
    responses = [
        SimpleNamespace(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": "Coupé"}, "finish_reason": "length"}]},
        ),
        SimpleNamespace(status_code=401, text="unauthorized"),
    ]
    monkeypatch.setattr(client, "_perform_request", lambda *_a, **_k: responses.pop(0))

    with pytest.raises(Exception, match="interrompue"):
        client.send_request_sync("Corrige", "Texte", reasoning_mode="on")
    with pytest.raises(Exception) as error:
        client.send_request_sync("Corrige", "Texte")

    assert str(error.value).count("Erreur") == 1
    assert "401" in str(error.value)
    client.close()

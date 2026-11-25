"""Regressions around local servers, their addresses, and text shown as typed."""

import json

import pytest
import requests
from PySide6.QtWidgets import QApplication, QMenu

from supermenu_core.api import lmstudio_transport as transport
from supermenu_core.api import openai_client as client_module
from supermenu_core.api.model_capabilities import choose_reasoning_option
from supermenu_core.api.openai_client import OpenAIClient
from supermenu_core.api.providers import common
from supermenu_core.config.prompts import repair_prompt_collection
from supermenu_core.ui.controls import plain_tooltip, populate_prompt_menu
from supermenu_core.utils.validators import Validators

from test_model_routing import Socket
from test_provider_requests import FakeSettings


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


# Proxy -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "local"),
    [
        ("http://localhost:11434", True),
        ("http://127.0.0.1:1234/v1", True),
        ("http://[::1]:11434", True),
        ("http://192.168.1.20:1234", True),
        ("http://10.0.0.5:11434/api", True),
        ("http://gpu-box:11434", True),
        ("http://studio.local:1234", True),
        ("https://api.openai.com/v1/chat/completions", False),
        ("https://api.anthropic.com/v1/messages", False),
        ("https://llm.example.com/v1", False),
        ("http://8.8.8.8:1234", False),
        ("", False),
    ],
)
def test_local_addresses_are_recognised(url, local):
    assert common.is_local_url(url) is local


def test_local_servers_are_never_reached_through_the_proxy(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example:3128")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:3128")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    session = client_module._session()

    def proxies_for(url):
        return session.merge_environment_settings(url, {}, None, None, None)["proxies"]

    # The selected text and the endpoint token stay on the local network.
    assert proxies_for("http://localhost:11434/api/chat") == {}
    assert proxies_for("http://192.168.1.20:1234/api/v1/chat") == {}
    # Online providers keep the proxy configured for Internet access.
    assert "proxy.example" in proxies_for(
        "https://api.openai.com/v1/chat/completions"
    ).get("https", "")
    assert "proxy.example" in proxies_for(
        "https://api.anthropic.com/v1/messages"
    ).get("https", "")


# Addresses ---------------------------------------------------------------


@pytest.mark.parametrize(
    "typed",
    [
        "http://localhost:11434",
        "http://localhost:11434/",
        "http://localhost:11434/api",
        "http://localhost:11434/api/chat",
        "http://localhost:11434/api/tags",
        "http://localhost:11434/api/generate",
        # The address Ollama documents for OpenAI clients.
        "http://localhost:11434/v1",
        "http://localhost:11434/v1/chat/completions",
    ],
)
def test_every_common_form_of_an_ollama_address_reaches_the_same_server(typed):
    assert common.models_base_url(typed, True) == "http://localhost:11434"
    client = OpenAIClient(
        FakeSettings("ollama", "qwen3", typed), api_key="test", allow_images=False
    )
    assert client.api_url == "http://localhost:11434/api/chat"
    client.close()


@pytest.mark.parametrize(
    "url",
    ["http://metadata:8080", "http://bigdata:11434/v1", "http://my-data:1234"],
)
def test_server_names_ending_in_data_are_accepted(url):
    assert Validators.validate_url(url) == (True, "")


def test_log_label_never_carries_the_credentials_of_an_address():
    label = common.endpoint_label("https://user:s3cret@host.example:8443/v1")

    assert label == "https://host.example:8443/v1"
    assert "s3cret" not in label and "user" not in label
    assert common.endpoint_label("http://[::1]:11434") == "http://[::1]:11434"
    assert common.endpoint_label("") == "(adresse absente)"


# Unreachable server ------------------------------------------------------


def test_stopped_local_server_is_reported_at_once_in_french(monkeypatch):
    calls = []

    def refused(*_args, **_kwargs):
        calls.append(1)
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(client_module._SESSION, "post", refused)
    monkeypatch.setattr(client_module.time, "sleep", lambda _s: pytest.fail("attente"))
    client = OpenAIClient(
        FakeSettings("ollama", "qwen3", "http://user:pw@localhost:11434"),
        api_key="test",
        allow_images=False,
    )

    with pytest.raises(Exception) as error:
        client._make_request_with_retry({}, {"model": "qwen3"}, timeout=60)

    # One attempt: a server that is not running will not answer a retry.
    assert len(calls) == 1
    message = str(error.value)
    assert "Serveur injoignable" in message and "http://localhost:11434" in message
    assert "pw" not in message
    client.close()


def test_online_provider_connection_errors_are_still_retried(monkeypatch):
    calls = []

    def offline(*_args, **_kwargs):
        calls.append(1)
        raise requests.exceptions.ConnectionError("offline")

    monkeypatch.setattr(client_module._SESSION, "post", offline)
    client = OpenAIClient(FakeSettings(), api_key="test", retry_delay=0)

    with pytest.raises(Exception, match="Connexion au fournisseur impossible"):
        client._make_request_with_retry({}, {"model": "x"}, timeout=60)

    assert len(calls) == 3
    client.close()


# Reasoning ---------------------------------------------------------------


def test_no_reasoning_on_a_model_without_off_means_its_lightest_level():
    options = ["low", "medium", "high"]

    assert choose_reasoning_option(options, "none", "medium") == "low"
    assert choose_reasoning_option(options, "off", "high") == "low"
    # A model that can turn reasoning off still does.
    assert choose_reasoning_option(["off", "on"], "none", "on") == "off"
    # No stated preference: the model's own default.
    assert choose_reasoning_option(options, None, "medium") == "medium"


@pytest.mark.parametrize("stop", ["failed", "modelUnloaded"])
def test_generation_aborted_on_the_device_is_an_error_not_an_answer(monkeypatch, stop):
    import websocket

    socket = Socket(stop=stop)
    monkeypatch.setattr(websocket, "create_connection", lambda *_a, **_k: socket)

    with pytest.raises(RuntimeError, match="arrêté avant la fin"):
        transport.targeted_completion(
            "http://localhost:1234", None, {"model": "gemma", "input": "Text"}, None
        )


# Text shown as typed -----------------------------------------------------


def test_ampersand_in_a_prompt_name_is_shown_in_the_menu(qt_app):
    menu = QMenu()
    populate_prompt_menu(
        menu,
        {"rd": {"name": "R&D", "position": 1}, "qr": {"name": "Questions & réponses", "position": 2}},
        lambda prompt_id: prompt_id,
    )

    labels = [action.text().replace("&&", "&") for action in menu.actions()]
    assert labels == ["R&D", "Questions & réponses"]
    # No letter is taken as a keyboard mnemonic.
    assert all(action.shortcut().isEmpty() for action in menu.actions())
    assert [action.text() for action in menu.actions()] == [
        "R&&D",
        "Questions && réponses",
    ]
    menu.deleteLater()


def test_tooltips_show_server_and_prompt_text_literally(qt_app):
    from PySide6 import QtGui

    hostile = '<img src="file:///etc/passwd">Poste <b>distant</b>'
    safe = plain_tooltip(hostile)

    assert "<img" not in safe and "&lt;img" in safe
    assert QtGui.Qt.mightBeRichText(safe)  # Rendered, showing the raw text.
    # Ordinary text is left alone, "&" included.
    assert plain_tooltip("R&D — Mac Studio") == "R&D — Mac Studio"
    assert plain_tooltip(None) == ""


# Prompt library ----------------------------------------------------------


def test_duplicate_hotkey_is_reported_so_the_library_is_backed_up_not_rewritten():
    raw = {
        "a": {"name": "Premier", "prompt": "x", "status": "s", "hotkey": "Ctrl+Alt+K"},
        "b": {"name": "Second", "prompt": "y", "status": "s", "hotkey": "ctrl+alt+k"},
    }

    prompts, problems = repair_prompt_collection(json.loads(json.dumps(raw)))

    assert prompts["a"]["hotkey"] == "Ctrl+Alt+K"
    assert prompts["b"]["hotkey"] == ""
    assert len(problems) == 1
    assert "Second" in problems[0] and "Premier" in problems[0]

"""Endpoint and model validators must accept real LAN servers (finding 21)."""

import pytest

from supermenu_core.utils.validators import Validators


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434",
        "http://127.0.0.1:1234/v1",
        "https://api.example.com/v1/chat/completions",
        "http://DESKTOP-AB12CD:1234",
        "http://gpu-box:11434",
        "http://ollama:11434",
        "http://host.docker.internal:11434",
        "http://my_server.lan:8080/api/v1",
        "http://[::1]:1234",
        "http://192.168.1.20:11434/",
        "  http://localhost:1234  ",
    ],
)
def test_lan_and_container_endpoints_are_accepted(url):
    assert Validators.validate_url(url) == (True, "")


@pytest.mark.parametrize(
    "url",
    [
        "",
        None,
        "localhost:11434",
        "ftp://localhost:11434",
        "http://",
        "http://:1234",
        "http://999.999.1.1:80",
        "http://exa mple.com",
        "http://localhost:99999",
        "http://localhost:abc",
        "http://-bad-.example.com",
        "http://[not-ipv6]:1234",
        "http://localhost/?next=javascript:alert(1)",
    ],
)
def test_malformed_or_dangerous_endpoints_are_rejected(url):
    valid, message = Validators.validate_url(url)

    assert valid is False
    assert message


@pytest.mark.parametrize(
    "model",
    [
        "qwen3:8b",
        "qwen/qwen3-8b@q4_k_m",
        "hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M",
        "openai/gpt-oss-20b",
        "my model:2",
    ],
)
def test_catalog_model_identifiers_are_accepted(model):
    assert Validators.validate_model_name(model) == (True, "")


@pytest.mark.parametrize("model", ["", None, "a", "bad\nname", "x" * 257])
def test_empty_short_or_control_character_models_are_rejected(model):
    valid, message = Validators.validate_model_name(model)

    assert valid is False
    assert message

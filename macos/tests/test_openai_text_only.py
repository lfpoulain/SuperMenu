from src.api.openai_client import OpenAIClient


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
    data = client._build_request_data("Corrige", "Bonjour")
    assert data["messages"] == [
        {"role": "user", "content": "Corrige\n\nBonjour"}
    ]
    assert "image" not in str(data).casefold()


def test_ollama_payload_is_text_only():
    client = OpenAIClient(DummySettings("ollama"), api_key=None)
    data = client._build_request_data("Résume", "Un texte")
    assert data["messages"][0]["content"] == "Résume\n\nUn texte"
    assert "images" not in data["messages"][0]


def test_lm_studio_payload_is_text_only():
    client = OpenAIClient(DummySettings("lmstudio"), api_key=None)
    data = client._build_request_data("Explique", "Un texte")
    assert data["input"] == "Explique\n\nUn texte"
    assert isinstance(data["input"], str)


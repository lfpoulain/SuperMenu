"""Integration follow-ups on Windows (findings 25, 29, 43, 51, 55, 67, 100)."""

import os
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

import supermenu_core.api.openai_client as shared_client
from src.api import foundry_worker
from src.api.foundry_client import FoundryService
from src.api.foundry_worker import FoundryRuntime, LocalError
from src.config import settings as settings_module
from src.config.foundry_models import FOUNDRY_MODELS
from src.config.settings import Settings
from src.utils import context_menu as context_menu_module
from src.utils import hotkey_manager as hotkeys
from src.utils.context_menu import ContextMenuManager


def _app():
    return QApplication.instance() or QApplication([])


class FakeSettings:
    def __init__(self, prompts=None):
        self.prompts = prompts or {}

    def get_ai_provider(self):
        return "openai"

    def get_api_key(self):
        return "key"

    def get_use_custom_endpoint(self):
        return False

    def get_custom_endpoint(self):
        return ""

    def get_custom_endpoint_type(self):
        return "ollama"

    def get_custom_model(self):
        return ""

    def get_model(self):
        return "gpt-5.6-sol"

    def get_reasoning_effort(self):
        return "none"

    def get_prompts(self):
        return dict(self.prompts)

    def get_prompt(self, prompt_id):
        return self.prompts.get(prompt_id)

    def get_voice_prompts(self):
        return {}

    def get_dictation_auto_insert(self):
        return False

    def get_dictation_correct_before_insert(self):
        return True

    def sync(self):
        pass


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module.os.path, "expanduser", lambda _path: str(tmp_path))
    instance = Settings()
    yield instance
    instance.settings.clear()
    instance.settings.sync()


# Finding 25 -- previewing another model never rewrites the saved effort.


def test_previewing_another_model_keeps_the_saved_effort(isolated_settings):
    isolated_settings.set_model("gpt-5.6-sol")
    isolated_settings.set_openai_reasoning_effort("max")

    # GPT-5.4 has no "max": the preview shows the closest supported effort.
    assert isolated_settings.get_openai_reasoning_effort("gpt-5.4") == "xhigh"

    assert isolated_settings.settings.value("openai_reasoning_effort") == "max"
    assert isolated_settings.get_openai_reasoning_effort() == "max"


def test_the_saved_model_still_migrates_an_unsupported_effort(isolated_settings):
    isolated_settings.set_model("gpt-5.4")
    isolated_settings.settings.setValue("openai_reasoning_effort", "max")

    assert isolated_settings.get_openai_reasoning_effort("gpt-5.4") == "xhigh"
    assert isolated_settings.settings.value("openai_reasoning_effort") == "xhigh"


# Finding 29 -- an error is never shown as a success nor insertable.


def test_request_error_is_shown_as_an_error_that_cannot_be_written():
    _app()
    manager = ContextMenuManager(FakeSettings())
    window = manager.response_window
    window.set_response = lambda *_args: pytest.fail("une erreur n'est pas une réponse")
    try:
        manager.on_request_error("HTTP 401")

        assert window.has_error
        assert window.response_text.toPlainText() == "Erreur: HTTP 401"
        assert "Terminé" not in window.status_label.text()
        assert not window.write_button.isEnabled()
        assert window.copy_button.isEnabled()
    finally:
        manager.close()


# Finding 43 -- dictation correction follows the « Corriger » reasoning mode.


def test_dictation_correction_reads_the_corriger_reasoning_mode(monkeypatch):
    _app()
    settings = FakeSettings({"corriger": {"reasoning_mode": "off"}})
    manager = ContextMenuManager(settings)
    created = []

    class FakeSession:
        def __init__(self, *args, **kwargs):
            created.append(kwargs)

        def start_voice_recognition(self):
            pass

        def cleanup(self):
            pass

    monkeypatch.setattr(
        "supermenu_core.audio.dictation_flow.PlainDictationSession", FakeSession
    )
    monkeypatch.setattr(context_menu_module, "speech_options", lambda _settings: {})
    try:
        manager._handle_voice_action(target=object())

        mode = created[0]["correction_reasoning_mode"]
        assert callable(mode) and mode() == "off"
        # Read at insertion time: a later change of the prompt applies.
        settings.prompts["corriger"]["reasoning_mode"] = "on"
        assert mode() == "on"
        settings.prompts.clear()
        assert mode() == "default"
    finally:
        manager.voice_recognition = None
        manager.close()


# Finding 51 -- saving the settings probes the servers again.


def test_updating_the_client_forgets_shared_capability_probes():
    _app()
    manager = ContextMenuManager(FakeSettings())
    try:
        shared_client._remember_capabilities(("ollama", "http://localhost:11434", "m"), {"vision": True})

        manager.update_client_config()

        assert shared_client._cached_capabilities(("ollama", "http://localhost:11434", "m")) is None
    finally:
        manager.close()


# Finding 55 -- Shift alone would swallow ordinary typing system-wide.


@pytest.fixture
def layout(monkeypatch):
    mapping = {"k": 0x4B, "1": 0x31}
    monkeypatch.setattr(hotkeys, "_USER32", SimpleNamespace(VkKeyScanW=mapping.__getitem__))


@pytest.mark.parametrize("label", ["Shift+K", "Shift+1", "Shift+Space", "Shift+Enter", "Shift+Left"])
def test_shift_alone_is_refused_for_typing_keys(layout, label):
    modifiers, vk, error = hotkeys._parse_hotkey_to_win32(label)

    assert modifiers is None and vk is None
    assert "Shift seul" in error


@pytest.mark.parametrize(
    "label, expected_modifiers",
    [
        ("Shift+F5", hotkeys._MOD_SHIFT),
        ("Ctrl+Shift+K", hotkeys._MOD_CONTROL | hotkeys._MOD_SHIFT),
        ("Alt+Shift+K", hotkeys._MOD_ALT | hotkeys._MOD_SHIFT),
        ("Alt+K", hotkeys._MOD_ALT),
        ("Ctrl+Alt+M", hotkeys._MOD_CONTROL | hotkeys._MOD_ALT),
    ],
)
def test_other_combinations_stay_accepted(layout, monkeypatch, label, expected_modifiers):
    monkeypatch.setattr(
        hotkeys,
        "_USER32",
        SimpleNamespace(VkKeyScanW={"k": 0x4B, "m": 0x4D}.__getitem__),
    )
    modifiers, vk, error = hotkeys._parse_hotkey_to_win32(label)

    assert error == ""
    assert modifiers == expected_modifiers


# Finding 67 -- stable builds are not told to reinstall a beta.


def test_engine_start_failure_asks_to_reinstall_supermenu(tmp_path):
    app = _app()
    service = FoundryService(command=(str(tmp_path / "absent-worker.exe"), []))
    errors = []
    service.failed.connect(lambda *args: errors.append(args))
    try:
        service.submit("generate", request_id="r1")
        deadline = time.monotonic() + 10
        while not errors and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.005)

        assert errors and errors[0][0] == "r1"
        assert "Réinstallez SuperMenu." in errors[0][1]
        assert "bêta" not in errors[0][1]
    finally:
        service.close()


def test_missing_bundled_runtime_asks_to_reinstall_supermenu(tmp_path, monkeypatch):
    monkeypatch.setattr(foundry_worker.sys, "frozen", True, raising=False)
    monkeypatch.setattr(foundry_worker.sys, "_MEIPASS", str(tmp_path), raising=False)

    with pytest.raises(LocalError) as error:
        foundry_worker.verify_bundled_runtime()

    assert "réinstallez SuperMenu" in str(error.value)
    assert "bêta" not in str(error.value)


# Finding 100 -- the advice follows the Foundry catalogue.


def test_unknown_model_advice_lists_the_catalogue(tmp_path):
    expected = "Choisissez Qwen3.5 4B ou Qwen3.5 9B dans les réglages."
    assert len(FOUNDRY_MODELS) == 2
    assert foundry_worker.unknown_model_message() == expected

    with pytest.raises(LocalError) as error:
        FoundryRuntime(root=tmp_path).model("modele-absent")

    assert str(error.value) == expected


def test_unknown_model_advice_grows_with_the_catalogue(monkeypatch):
    catalogue = {
        "a": {"label": "Modèle A — léger"},
        "b": {"label": "Modèle B — qualité"},
        "c": {"label": "Modèle C"},
    }
    monkeypatch.setattr(foundry_worker, "FOUNDRY_MODELS", catalogue)

    assert foundry_worker.unknown_model_message() == (
        "Choisissez Modèle A, Modèle B ou Modèle C dans les réglages."
    )

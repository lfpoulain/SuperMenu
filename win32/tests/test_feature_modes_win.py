"""Advanced and experimental features on Windows: shown, registered and used
only when switched on, applied without restarting, never deleting anything."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QApplication

from src.api import foundry_client
from src.api.foundry_client import FoundryClient
from src.audio import speech_backend
from src.config import settings as settings_module
from src.config.settings import Settings
from src.ui import main_window
from src.ui.main_window import MainWindow
from src.utils import context_menu
from src.utils import hotkey_manager
from src.utils.context_menu import ContextMenuManager
from supermenu_core.audio.backends import SpeechBackend
from supermenu_core.config import feature_modes
from supermenu_core.ui.dictation_settings import GENERAL_MODEL_HINT, PROMPT_MODEL_HINT

LM_LINK_TARGET = {"provider": "custom", "model": "gemma", "device": "apple"}
STORED_KEYS = (
    "prompts",
    "voice_prompts",
    "voice_hotkey",
    "screenshot_hotkey",
    "dictation_hotkey",
    "text_idle_seconds",
    "speech_idle_seconds",
)


def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def new_install(monkeypatch, tmp_path):
    """A first launch: both switches start off, written in ~/SuperMenu.ini."""
    _app()
    monkeypatch.setattr(feature_modes, "NEW_INSTALL_ENABLED", False)
    monkeypatch.setattr(settings_module.os.path, "expanduser", lambda _path: str(tmp_path))
    monkeypatch.setattr(Settings, "get_api_key", lambda _self: "")
    monkeypatch.setattr(Settings, "get_custom_endpoint_api_key", lambda _self: "")
    monkeypatch.setattr("supermenu_core.ui.speech_settings.microphones", lambda: [])
    settings = Settings()
    assert not settings.get_advanced_features_enabled()
    assert not settings.get_experimental_features_enabled()
    settings.ini_path = tmp_path / "SuperMenu.ini"
    return settings


def _raw_values(settings):
    settings.sync()
    store = QSettings(str(settings.ini_path), QSettings.Format.IniFormat)
    return {key: store.value(key) for key in STORED_KEYS}


# --- Shortcut managers ------------------------------------------------------


@pytest.fixture
def registry(monkeypatch):
    registered = []
    monkeypatch.setattr(
        hotkey_manager,
        "_parse_hotkey_to_win32",
        lambda hotkey: (3, 0x41, "") if hotkey else (0, 0, "Aucun raccourci"),
    )

    def register(_modifiers, _vk, callback):
        registered.append(callback)
        return len(registered), ""

    monkeypatch.setattr(hotkey_manager._REGISTRY, "register", register)
    monkeypatch.setattr(hotkey_manager._REGISTRY, "unregister", lambda _id: None)
    return registered


def test_disabled_experimental_features_do_not_hold_their_shortcuts(new_install, registry):
    settings = new_install
    settings.set_dictation_hotkey("Ctrl+Alt+D")
    managers = {
        "main": hotkey_manager.HotkeyManager(settings),
        "custom": hotkey_manager.HotkeyManager(settings, custom_hotkey=True),
        "voice": hotkey_manager.HotkeyManager(settings, voice_hotkey=True),
        "screenshot": hotkey_manager.HotkeyManager(settings, screenshot_hotkey=True),
        "dictation": hotkey_manager.HotkeyManager(settings, dictation_hotkey=True),
    }
    try:
        assert len(registry) == 2
        assert managers["main"].registered and managers["custom"].registered
        for name in ("voice", "screenshot", "dictation"):
            manager = managers[name]
            # Inactive by choice: not an error to report at startup.
            assert not manager.registered
            assert manager.last_error == ""
            assert manager.register_hotkey() is True
            assert not manager.registered
        # The stored shortcuts are untouched.
        assert settings.get_voice_hotkey() == "Ctrl+Alt+²"
        assert settings.get_dictation_hotkey() == "Ctrl+Alt+D"

        settings.set_experimental_features_enabled(True)
        for name in ("voice", "screenshot", "dictation"):
            assert managers[name].register_hotkey() is True
            assert managers[name].registered
        assert len(registry) == 5
    finally:
        for manager in managers.values():
            manager.close()


def test_prompt_shortcuts_are_kept_but_not_registered_without_advanced_features(
    new_install, registry
):
    settings = new_install
    settings.update_prompt(
        "corriger", "Corriger", "Corrige", "Correction", hotkey="Ctrl+Alt+K"
    )
    manager = hotkey_manager.PromptHotkeyManager(settings)
    try:
        assert registry == []
        assert manager.refresh_hotkeys() == (True, {})
        assert registry == [] and manager.errors == {}
        assert settings.get_prompt("corriger")["hotkey"] == "Ctrl+Alt+K"

        settings.set_advanced_features_enabled(True)
        assert manager.refresh_hotkeys() == (True, {})
        assert len(registry) == 1
    finally:
        manager.close()


# --- Context menu -----------------------------------------------------------


class Client(QObject):
    request_started_scoped = Signal(str, bool)
    request_finished_scoped = Signal(str, str, bool, object)
    request_error_scoped = Signal(str, str)

    def __init__(self, settings):
        super().__init__()
        self.settings, self.sent, self.closed = settings, [], False

    def send_request(self, *args, **kwargs):
        self.sent.append((args, kwargs))

    def close(self):
        self.closed = True


@pytest.fixture
def menu_manager(new_install, monkeypatch):
    created = []

    def create(manager, config=None):
        client = Client(config or manager.settings)
        created.append(client)
        return client

    monkeypatch.setattr(ContextMenuManager, "_create_api_client", create)
    manager = ContextMenuManager(new_install)
    manager.created_clients = created
    yield manager
    manager.close()


def test_prompt_model_is_ignored_without_advanced_features(menu_manager):
    manager, settings = menu_manager, menu_manager.settings
    settings.update_prompt(
        "corriger", "Corriger", "Corrige", "Correction",
        model_target={"provider": "openai", "model": "gpt-5.6-luna"},
    )
    stored = settings.get_prompt("corriger")

    manager._send_request("Corrige", "Texte", model_target=stored["model_target"])

    # The general client answers: no client is built for the prompt's model.
    assert len(manager.created_clients) == 1
    assert manager.created_clients[0].sent
    assert manager.response_window.last_model_target == {}
    assert settings.get_prompt("corriger") == stored

    settings.set_advanced_features_enabled(True)
    manager._send_request("Corrige", "Texte", model_target=stored["model_target"])
    assert len(manager.created_clients) == 2
    assert manager.created_clients[1].settings.get_model() == "gpt-5.6-luna"


def test_disabled_features_ignore_queued_shortcuts_and_menu_entries(
    menu_manager, monkeypatch
):
    manager = menu_manager
    calls = []
    monkeypatch.setattr(
        context_menu.PasteTarget, "capture", staticmethod(lambda: calls.append("capture"))
    )
    monkeypatch.setattr(context_menu, "capture_screen", lambda *_a: calls.append("screen"))
    monkeypatch.setattr(manager, "_begin_menu_session", lambda **_kw: calls.append("menu"))
    monkeypatch.setattr(
        manager, "_create_voice_recognition", lambda **_kw: calls.append("voice")
    )
    monkeypatch.setattr(
        "src.ui.prompt_dialog.PromptDialog.show_prompt_dialog",
        staticmethod(lambda *_a: calls.append("dialog")),
    )
    monkeypatch.setattr(
        context_menu.SafeDialogs, "show_critical", lambda *_a: calls.append("error")
    )
    monkeypatch.setattr(
        context_menu.SafeDialogs, "show_information", lambda *_a: calls.append("info")
    )
    target = object()

    manager.show_voice_menu()
    manager._handle_voice_action(target=target)
    manager._handle_voice_prompt_action("dictee", target=target)
    manager._handle_voice_godmode_action(target=target)
    manager._handle_screenshot_action()
    manager.start_instant_dictation()
    manager.run_prompt_hotkey("corriger")

    assert calls == []
    assert manager.voice_recognition is None


def test_instant_dictation_never_adopts_an_older_session_when_disabled(menu_manager):
    manager = menu_manager

    class Session:
        is_recording = is_processing = _delivery_busy = False
        stopped = False

        def stop_listening(self):
            self.stopped = True

        def cleanup(self):
            pass

    older = Session()
    manager.voice_recognition = older

    manager.start_instant_dictation()
    manager.finish_instant_dictation()

    assert manager.voice_recognition is older
    assert getattr(manager, "_instant_session", None) is None
    assert not older.stopped


def test_retrying_a_screenshot_needs_the_experimental_features(menu_manager):
    manager, settings = menu_manager, menu_manager.settings
    client = manager.created_clients[0]
    window = manager.response_window
    window.store_request("Décris cette image", "data:image/png;base64,AAAA")

    window.retry_request()

    # The image is never sent again while the feature is off.
    assert client.sent == []
    assert window.has_error
    assert "Fonctions expérimentales" in window.response_text.toPlainText()
    assert window.retry_button.isEnabled()
    # The request is kept: it can be retried once the feature returns.
    assert window.get_last_request() == ("Décris cette image", "data:image/png;base64,AAAA")

    # A text request is retried as before.
    window.store_request("Corrige", "Texte")
    window.retry_request()
    assert len(client.sent) == 1
    assert client.sent[0][0][:2] == ("Corrige", "Texte")

    settings.set_experimental_features_enabled(True)
    window.store_request("Décris cette image", "data:image/png;base64,AAAA")
    window.retry_request()
    assert len(client.sent) == 2
    assert client.sent[1][0][:2] == ("Décris cette image", "data:image/png;base64,AAAA")


# --- Local model retention ---------------------------------------------------


class FakeService(QObject):
    completed = Signal(str, object)
    failed = Signal(str, str)
    progress = Signal(str, object)

    def __init__(self):
        super().__init__()
        self.idle = []

    def set_idle_seconds(self, seconds):
        self.idle.append(seconds)


def test_local_models_use_the_default_retention_without_advanced_features(
    new_install, monkeypatch
):
    settings = new_install
    settings.set_text_idle_seconds(-1)
    settings.set_speech_idle_seconds(0)
    monkeypatch.setattr(foundry_client, "platform_error", lambda: "")
    monkeypatch.setattr(speech_backend, "worker_command", lambda: ("worker.exe", ["--foundry-worker"]))
    service = FakeService()

    FoundryClient(settings, service).close()
    backend = speech_backend.create_speech_backend(settings, {"provider": "foundry"})
    assert service.idle == [300]
    assert backend.idle_seconds == 300

    settings.set_advanced_features_enabled(True)
    FoundryClient(settings, service).close()
    backend = speech_backend.create_speech_backend(settings, {"provider": "foundry"})
    assert service.idle == [300, -1]
    assert backend.idle_seconds == 0
    # The stored delays were never rewritten.
    assert settings.get_text_idle_seconds() == -1
    assert settings.get_speech_idle_seconds() == 0


# --- Main window --------------------------------------------------------------


class FakeHotkeyManager(QObject):
    registration_failed = Signal(str)

    def __init__(self, name, events, getter, feature):
        super().__init__()
        self.name, self.events, self.getter = name, events, getter
        self.feature_name = feature
        self.hotkey = getter()
        self.registered = True
        self._last_register_error = ""
        self.refuse_with = ""

    @property
    def last_error(self):
        return self._last_register_error

    def unregister_hotkey(self):
        self.events.append(f"{self.name}:unregister")
        self.registered = False

    def register_hotkey(self):
        self.events.append(f"{self.name}:register")
        self.hotkey = self.getter()
        self.registered = not self.refuse_with
        self._last_register_error = self.refuse_with
        return self.registered


class FakePromptHotkeyManager:
    def __init__(self, events):
        self.events = events
        self.errors = {}
        self.refresh_errors = {}

    def unregister_hotkeys(self):
        self.events.append("prompts:unregister")

    def refresh_hotkeys(self):
        self.events.append("prompts:refresh")
        self.errors = dict(self.refresh_errors)
        return not self.errors, dict(self.errors)


def _window(settings):
    events = []
    managers = {
        "main": FakeHotkeyManager("main", events, settings.get_hotkey, "Menu principal"),
        "voice": FakeHotkeyManager("voice", events, settings.get_voice_hotkey, "Menu vocal"),
        "custom": FakeHotkeyManager("custom", events, settings.get_custom_hotkey, "Mode personnalisé"),
        "screenshot": FakeHotkeyManager(
            "screenshot", events, settings.get_screenshot_hotkey, "Capture d’écran"
        ),
        "dictation": FakeHotkeyManager("dictation", events, settings.get_dictation_hotkey, "Dictée"),
    }
    prompts = FakePromptHotkeyManager(events)
    window = MainWindow(
        settings,
        hotkey_manager=managers["main"],
        voice_hotkey_manager=managers["voice"],
        screenshot_hotkey_manager=managers["screenshot"],
        custom_hotkey_manager=managers["custom"],
        prompt_hotkey_manager=prompts,
        dictation_hotkey_manager=managers["dictation"],
    )
    return window, managers, prompts, events


@pytest.fixture
def messages(monkeypatch):
    shown = {"information": [], "warning": [], "question": []}
    monkeypatch.setattr(
        main_window.QMessageBox, "information", lambda *a, **_k: shown["information"].append(a)
    )
    monkeypatch.setattr(
        main_window.QMessageBox, "warning", lambda *a, **_k: shown["warning"].append(a)
    )

    def question(*args, **_kwargs):
        shown["question"].append(args)
        return main_window.QMessageBox.StandardButton.Yes

    monkeypatch.setattr(main_window.QMessageBox, "question", question)
    return shown


def _visibility(window):
    form = window.text_prompt_form
    voice_index = window.tab_widget.indexOf(window.voice_prompt_editor)
    return {
        "voice_tab": window.tab_widget.isTabVisible(voice_index),
        "voice_page": window.settings_panel.is_page_visible("voice"),
        "voice_hotkey": window.shortcut_settings.is_shortcut_visible(window.voice_hotkey_label),
        "screenshot_hotkey": window.shortcut_settings.is_shortcut_visible(window.screenshot_hotkey_label),
        "dictation_shortcut": not window.dictation_shortcut_settings.isHidden(),
        "screenshot_group": not window.screenshot_group.isHidden(),
        "voice_note": not window.foundry_group.voice_engine_note.isHidden(),
        "prompt_model": form.form.isRowVisible(form.model_choice),
        "prompt_hotkey": form.form.isRowVisible(form.hotkey_row),
        "voice_prompt_model": window.voice_prompt_editor.is_advanced_visible(),
        "text_retention": not window.foundry_group.memory_options.isHidden(),
        "speech_retention": window.speech_settings.is_retention_visible(),
    }


EXPERIMENTAL = ("voice_tab", "voice_page", "voice_hotkey", "screenshot_hotkey",
                "dictation_shortcut", "screenshot_group", "voice_note")
ADVANCED = ("prompt_model", "prompt_hotkey", "voice_prompt_model", "text_retention",
            "speech_retention")


def _expected(advanced, experimental):
    return {
        **{key: experimental for key in EXPERIMENTAL},
        **{key: advanced for key in ADVANCED},
    }


def test_new_installation_shows_only_the_essentials(new_install):
    window, _managers, _prompts, events = _window(new_install)
    try:
        assert _visibility(window) == _expected(False, False)
        form = window.text_prompt_form
        # Reasoning is part of the standard prompt editor.
        assert form.form.isRowVisible(form.reasoning)
        assert window.shortcut_settings.is_shortcut_visible(window.hotkey_label)
        assert window.shortcut_settings.is_shortcut_visible(window.custom_hotkey_label)
        assert window.foundry_group.hardware_options.toggle.text() == "Matériel du modèle"
        assert window.dictation_behavior.hint.text() == GENERAL_MODEL_HINT
        assert not window.feature_mode_settings.advanced_check.isChecked()
        assert not window.feature_mode_settings.experimental_check.isChecked()
        # Showing or hiding the interface never touches the shortcuts.
        assert events == []
    finally:
        window.deleteLater()


def test_updated_installation_keeps_every_feature_visible(new_install):
    new_install.set_advanced_features_enabled(True)
    new_install.set_experimental_features_enabled(True)
    window, _managers, _prompts, events = _window(new_install)
    try:
        assert _visibility(window) == _expected(True, True)
        assert window.foundry_group.hardware_options.toggle.text() == "Matériel et mémoire du modèle"
        assert window.dictation_behavior.hint.text() == PROMPT_MODEL_HINT
        assert events == []
    finally:
        window.deleteLater()


def test_switches_apply_live_and_never_rewrite_stored_settings(
    new_install, messages, monkeypatch
):
    settings = new_install
    settings.set_dictation_hotkey("Ctrl+Alt+D")
    settings.set_text_idle_seconds(-1)
    settings.set_speech_idle_seconds(0)
    settings.update_prompt(
        "corriger", "Corriger", "Corrige", "Correction",
        hotkey="Ctrl+Alt+K", model_target=LM_LINK_TARGET,
    )
    before = _raw_values(settings)
    window, _managers, _prompts, events = _window(settings)
    modes = window.feature_mode_settings
    try:
        window.tab_widget.setCurrentIndex(0)
        assert window.foundry_group.service.idle_seconds == 300

        modes.advanced_check.setChecked(True)
        modes.experimental_check.setChecked(True)
        window.app_save_button.click()

        assert _visibility(window) == _expected(True, True)
        assert events == [
            "prompts:unregister",
            "voice:register",
            "screenshot:register",
            "dictation:register",
            "prompts:refresh",
        ]
        assert len(messages["information"]) == 1 and messages["warning"] == []
        assert window.foundry_group.service.idle_seconds == -1
        assert window.speech_settings.resident.idle_seconds == 0
        assert settings.get_advanced_features_enabled()
        assert settings.get_experimental_features_enabled()

        # Advanced alone: only the prompt shortcuts are rebuilt.
        events.clear()
        modes.advanced_check.setChecked(False)
        window.app_save_button.click()
        # One prompt has its own model: turning the feature off asks first.
        assert len(messages["question"]) == 1
        assert events == ["prompts:unregister", "prompts:refresh"]
        assert _visibility(window) == _expected(False, True)
        assert window.foundry_group.service.idle_seconds == 300
        assert window.speech_settings.resident.idle_seconds == 300

        events.clear()
        modes.experimental_check.setChecked(False)
        window.app_save_button.click()
        assert _visibility(window) == _expected(False, False)
        assert events == [
            "prompts:unregister",
            "voice:register",
            "screenshot:register",
            "dictation:register",
            "prompts:refresh",
        ]
        assert len(messages["information"]) == 3 and messages["warning"] == []
        assert _raw_values(settings) == before
        assert settings.get_prompt("corriger")["model_target"] == LM_LINK_TARGET
        assert settings.get_prompt("corriger")["hotkey"] == "Ctrl+Alt+K"
    finally:
        window.deleteLater()


def test_declining_to_turn_advanced_off_keeps_prompt_models_in_use(
    new_install, messages, monkeypatch
):
    settings = new_install
    settings.set_advanced_features_enabled(True)
    settings.update_prompt(
        "corriger", "Corriger", "Corrige", "Correction", model_target=LM_LINK_TARGET,
    )
    window, _managers, _prompts, events = _window(settings)
    asked = []

    def decline(*args, **_kwargs):
        asked.append(args)
        return main_window.QMessageBox.StandardButton.No

    monkeypatch.setattr(main_window.QMessageBox, "question", decline)
    try:
        window.feature_mode_settings.advanced_check.setChecked(False)
        window.app_save_button.click()

        assert len(asked) == 1
        assert settings.get_advanced_features_enabled()
        assert window.feature_mode_settings.advanced_check.isChecked()
        assert _visibility(window) == _expected(True, False)
        # Nothing was applied: the shortcuts keep their registrations.
        assert events == []
        # The theme part of Apply still ends with its usual confirmation.
        assert len(messages["information"]) == 1 and messages["warning"] == []
    finally:
        window.deleteLater()


def test_apply_without_a_switch_change_leaves_the_shortcuts_alone(new_install, messages):
    window, _managers, _prompts, events = _window(new_install)
    try:
        window.app_save_button.click()
        assert events == []
        assert len(messages["information"]) == 1
    finally:
        window.deleteLater()


def test_voice_tab_is_left_before_it_is_hidden(new_install, messages):
    new_install.set_experimental_features_enabled(True)
    window, _managers, _prompts, _events = _window(new_install)
    try:
        voice_index = window.tab_widget.indexOf(window.voice_prompt_editor)
        window.tab_widget.setCurrentIndex(voice_index)
        window.settings_panel.select_page("voice")
        window.feature_mode_settings.experimental_check.setChecked(False)
        window.app_save_button.click()
        assert window.tab_widget.currentIndex() == 0
        assert not window.tab_widget.isTabVisible(voice_index)
        assert window.settings_panel.keys[window.settings_panel.navigation.currentRow()] != "voice"
    finally:
        window.deleteLater()


def test_shortcuts_refused_after_apply_are_listed_in_one_warning(new_install, messages):
    window, managers, prompts, events = _window(new_install)
    try:
        managers["voice"].refuse_with = "Raccourci déjà utilisé"
        prompts.refresh_errors = {"corriger": "Combinaison réservée"}
        window.feature_mode_settings.advanced_check.setChecked(True)
        window.feature_mode_settings.experimental_check.setChecked(True)
        window.app_save_button.click()

        assert messages["information"] == []
        assert len(messages["warning"]) == 1
        title, text = messages["warning"][0][1:3]
        assert title == "Raccourcis inactifs"
        assert "- Menu vocal (Ctrl+Alt+²) : Raccourci déjà utilisé" in text
        assert "- Corriger : Combinaison réservée" in text
        assert window.voice_hotkey_label.text() == "Ctrl+Alt+² (inactif)"
    finally:
        window.deleteLater()


def test_turning_experimental_off_stops_voice_checks_and_idle_model(
    new_install, messages, monkeypatch
):
    new_install.set_experimental_features_enabled(True)
    window, _managers, _prompts, _events = _window(new_install)
    speech = window.speech_settings
    calls = []
    monkeypatch.setattr(speech, "cancel", lambda *a, **kw: calls.append(("check", kw)))
    monkeypatch.setattr(
        speech.microphone_test, "cancel", lambda *a, **kw: calls.append(("microphone", kw))
    )
    monkeypatch.setattr(speech.resident, "unload_idle", lambda: calls.append(("model", {})))
    try:
        window.feature_mode_settings.experimental_check.setChecked(False)
        window.app_save_button.click()
        # Nothing was running: nothing is cancelled, the idle model unloads.
        assert calls == [("model", {})]
        # A dictation still running unloads its model as soon as it ends.
        assert speech.resident.idle_seconds == 0
        calls.clear()
        window.feature_mode_settings.experimental_check.setChecked(True)
        window.app_save_button.click()
        assert calls == []
    finally:
        window.deleteLater()


class FakeSpeechBackend(SpeechBackend):
    phase = "download"

    def __init__(self):
        super().__init__()
        self.cancelled = False

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True


def test_a_voice_download_stopped_by_the_switch_is_not_shown_running_again(
    new_install, messages
):
    new_install.set_experimental_features_enabled(True)
    window, _managers, _prompts, _events = _window(new_install)
    speech = window.speech_settings
    backend = FakeSpeechBackend()
    speech.backend_factory = lambda _options: backend
    try:
        speech.provider_combo.setCurrentIndex(speech.provider_combo.findData("foundry"))
        speech.prepare("download")
        backend.progress.emit("Téléchargement du modèle vocal", 45)
        assert speech.status.title.text() == "Téléchargement du modèle"
        assert speech.status.caption.text() == "45 % téléchargé"

        window.feature_mode_settings.experimental_check.setChecked(False)
        window.app_save_button.click()
        assert backend.cancelled and speech.backend is None

        window.feature_mode_settings.experimental_check.setChecked(True)
        window.app_save_button.click()
        # The interrupted download is reported as such, not as still running.
        assert speech.status.title.text() == "Opération annulée"
        assert speech.status.progress_bar.isHidden()
        assert speech.status.caption.isHidden()
        assert speech.cancel_button.isHidden()
        assert speech.check_button.isEnabled()
    finally:
        window.deleteLater()


def test_saving_a_prompt_keeps_its_hidden_model_and_shortcut(new_install, messages):
    settings = new_install
    settings.set_custom_endpoint_type("ollama")
    settings.update_prompt(
        "corriger", "Corriger", "Corrige", "Correction",
        hotkey="Ctrl+Alt+K", model_target=LM_LINK_TARGET,
    )
    window, _managers, _prompts, events = _window(settings)
    try:
        window.prompt_combo.setCurrentIndex(window.prompt_combo.findData("corriger"))
        window.prompt_text_input.setPlainText("Corrige sans changer le ton")
        # A stale edit of the hidden field is never saved.
        window.prompt_hotkey_input.setText("Ctrl+Alt+J")

        window.save_prompt()

        saved = settings.get_prompt("corriger")
        assert saved["prompt"] == "Corrige sans changer le ton"
        assert saved["hotkey"] == "Ctrl+Alt+K"
        assert saved["model_target"] == LM_LINK_TARGET
        assert messages["warning"] == []
        assert len(messages["information"]) == 1
        assert events == ["prompts:refresh"]
    finally:
        window.deleteLater()

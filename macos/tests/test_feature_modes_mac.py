"""Advanced and experimental features on macOS: hidden, inactive, never deleted."""

import json
import sys
from types import ModuleType, SimpleNamespace

import pytest
from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from src.audio import speech_backend
from src.config.settings import Settings
from src.ui import main_window as main_window_module
from src.ui.main_window import DICTATION_MENU_ENTRY, MainWindow
from src.ui.status_item import NativeStatusItem
from src.utils import context_menu
from src.utils.hotkey_manager import HotkeyManager, HotkeyService, PromptHotkeyManager
from src.utils.permissions import PermissionStatus
from supermenu_core.audio.backends import SpeechBackend
from supermenu_core.audio.dictation_shortcut import ReleaseBinding
from supermenu_core.audio.resident import ResidentSpeechService
from supermenu_core.config import feature_modes
from supermenu_core.config.model_target import ModelTargetSettings
from supermenu_core.ui.dictation_settings import GENERAL_MODEL_HINT, PROMPT_MODEL_HINT

LINK_TARGET = {"provider": "custom", "model": "qwen", "device": "poste-1"}
OPENAI_TARGET = {"provider": "openai", "model": "gpt-4.1-mini"}
RAW_KEYS = ("prompts", "voice_prompts", "dictation_hotkey", "speech_idle_seconds")
DICTATION = "<cmd>+<shift>+d"
MAIN = "<cmd>+<shift>+<space>"
CUSTOM = "<cmd>+<shift>+m"


class FakeListener:
    instances = []

    def __init__(self):
        self.bindings = {}
        self.alive = False
        self.__class__.instances.append(self)

    def replace_bindings(self, bindings):
        self.bindings = dict(bindings)

    def set_suspended(self, suspended):
        pass

    def start(self):
        self.alive = True

    def wait(self):
        return None

    def is_alive(self):
        return self.alive

    def stop(self):
        self.alive = False

    def join(self, timeout=None):
        pass


class FakeResident:
    def __init__(self):
        self.calls = []

    def set_idle_seconds(self, seconds):
        self.calls.append(("idle", seconds))

    def unload_idle(self):
        self.calls.append(("unload",))


class FakeClient(QObject):
    request_started_scoped = Signal(str, bool)
    request_finished_scoped = Signal(str, str, bool, object)
    request_error_scoped = Signal(str, str)

    def __init__(self, settings=None):
        super().__init__()
        self.settings = settings
        self.sent = []

    def send_request(self, *args, **kwargs):
        self.sent.append((args, kwargs))

    def close(self):
        pass


class FakeSession:
    is_recording = True
    is_processing = False

    def __init__(self):
        self.calls = []

    def cleanup(self):
        self.calls.append("cleanup")

    def deleteLater(self):
        self.calls.append("deleteLater")

    def stop_listening(self):
        self.calls.append("stop")


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def service():
    FakeListener.instances = []
    instance = HotkeyService(listener_factory=FakeListener)
    yield instance
    instance.close()


@pytest.fixture
def dialogs(monkeypatch):
    shown = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, text, *_args: shown.append(("information", title, text)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, text, *_args: shown.append(("warning", title, text)),
    )
    return shown


@pytest.fixture(autouse=True)
def _no_microphones(monkeypatch):
    monkeypatch.setattr("supermenu_core.ui.speech_settings.microphones", lambda: [])


def _new_install(tmp_path, monkeypatch, *, advanced=False, experimental=False):
    """A brand-new settings file (both switches off), then the given switches."""
    monkeypatch.setattr(feature_modes, "NEW_INSTALL_ENABLED", False)
    settings = Settings(config_path=str(tmp_path / "settings.ini"))
    assert not settings.get_advanced_features_enabled()
    assert not settings.get_experimental_features_enabled()
    settings.set_advanced_features_enabled(advanced)
    settings.set_experimental_features_enabled(experimental)
    settings.sync()
    return settings


def _first_prompt_id(settings):
    return min(
        settings.get_prompts().items(),
        key=lambda item: (item[1].get("position", 999), item[0]),
    )[0]


def _edit_first_prompt(settings, **fields):
    prompts = settings.get_prompts()
    prompt_id = _first_prompt_id(settings)
    prompts[prompt_id].update(fields)
    settings.set_prompts(prompts)
    settings.sync()
    return prompt_id


def _set_prompt_hotkeys(settings, *hotkeys):
    """Give the first prompts these shortcuts; return the first three ids."""
    prompts = settings.get_prompts()
    ids = sorted(prompts, key=lambda key: (prompts[key].get("position", 999), key))
    for prompt_id, hotkey in zip(ids, hotkeys):
        prompts[prompt_id]["hotkey"] = hotkey
    settings.set_prompts(prompts)
    settings.sync()
    return ids[:3]


def _select(window, prompt_id):
    for row in range(window.prompt_list.count()):
        item = window.prompt_list.item(row)
        if item.data(Qt.ItemDataRole.UserRole) == prompt_id:
            window.prompt_list.setCurrentItem(item)
            return
    raise AssertionError(prompt_id)


def _managers(settings, service):
    return {
        "hotkey_manager": HotkeyManager(settings, service=service),
        "custom_hotkey_manager": HotkeyManager(
            settings, custom_hotkey=True, service=service
        ),
        "dictation_hotkey_manager": HotkeyManager(
            settings, dictation_hotkey=True, service=service
        ),
        "prompt_hotkey_manager": PromptHotkeyManager(settings, service=service),
    }


def _bound():
    return set(FakeListener.instances[-1].bindings)


def _raw(settings):
    store = QSettings(settings.config_path, QSettings.Format.IniFormat)
    return {key: store.value(key) for key in RAW_KEYS}


def _close(window):
    """Close the window; the conftest destroys it once the test is over.

    A window left alive would be restyled by every later Apply.
    """
    window._quitting = True
    window.close()
    window.deleteLater()


def _granted(monkeypatch):
    monkeypatch.setattr(
        main_window_module,
        "current_permission_status",
        lambda: PermissionStatus(accessibility=True),
    )


def _fake_status_item(monkeypatch, *, with_entry_visibility=True):
    created = []

    class FakeNativeStatusItem:
        def __init__(self, icon_path, actions, parent=None):
            self.actions = actions
            self.visibility = []
            created.append(self)

        def hide(self):
            pass

    if with_entry_visibility:
        FakeNativeStatusItem.set_entry_visible = (
            lambda self, label, visible: self.visibility.append((label, visible))
        )
    module = ModuleType("src.ui.status_item")
    module.NativeStatusItem = FakeNativeStatusItem
    monkeypatch.setitem(sys.modules, "src.ui.status_item", module)
    monkeypatch.setattr(main_window_module, "sys", SimpleNamespace(platform="darwin"))
    return created


def _features_shown(window):
    form = window.text_prompt_form
    return {
        "voice_tab": window.tabs.isTabVisible(
            window.tabs.indexOf(window.voice_prompt_editor)
        ),
        "voice_page": window.settings_panel.is_page_visible("voice"),
        "dictation_shortcut": not window.dictation_shortcut_settings.isHidden(),
        "prompt_model": form.form.isRowVisible(form.model_choice),
        "prompt_hotkey": form.form.isRowVisible(form.hotkey_row),
        "voice_prompt_model": window.voice_prompt_editor.is_advanced_visible(),
        "voice_retention": window.speech_settings.is_retention_visible(),
    }


ALL_SHOWN = dict.fromkeys(
    (
        "voice_tab",
        "voice_page",
        "dictation_shortcut",
        "prompt_model",
        "prompt_hotkey",
        "voice_prompt_model",
        "voice_retention",
    ),
    True,
)
ALL_HIDDEN = dict.fromkeys(ALL_SHOWN, False)


# Configuration window.


def test_new_installation_hides_advanced_and_experimental_features(
    qt_app, tmp_path, monkeypatch
):
    window = MainWindow(_new_install(tmp_path, monkeypatch))
    try:
        assert _features_shown(window) == ALL_HIDDEN
        form = window.text_prompt_form
        # Per-prompt reasoning is not an advanced feature.
        assert form.form.isRowVisible(form.reasoning)
        assert window.dictation_behavior.hint.text() == GENERAL_MODEL_HINT
        assert not window.feature_mode_settings.advanced_check.isChecked()
        assert not window.feature_mode_settings.experimental_check.isChecked()
        # Only the voice page is hidden; the tab indexes never move.
        assert [
            key for key in window.settings_panel.keys
            if window.settings_panel.is_page_visible(key)
        ] == ["text", "shortcuts", "app"]
        assert window.tabs.indexOf(window.voice_prompt_editor) == 1
        assert window.tabs.indexOf(window.settings_tab) == 2
    finally:
        _close(window)


def test_updated_installation_keeps_every_feature_visible(qt_app, tmp_path):
    # The conftest makes this a settings file updated from an earlier version.
    window = MainWindow(Settings(config_path=str(tmp_path / "settings.ini")))
    try:
        assert _features_shown(window) == ALL_SHOWN
        assert window.dictation_behavior.hint.text() == PROMPT_MODEL_HINT
        assert window.feature_mode_settings.advanced_check.isChecked()
        assert window.feature_mode_settings.experimental_check.isChecked()
    finally:
        _close(window)


def test_apply_shows_and_hides_features_live_without_touching_saved_data(
    qt_app, tmp_path, monkeypatch, service, dialogs
):
    settings = _new_install(tmp_path, monkeypatch)
    settings.set_dictation_hotkey("Cmd+Shift+D")
    settings.set_speech_idle_seconds(-1)
    _edit_first_prompt(settings, hotkey="Cmd+Shift+1", model_target=OPENAI_TARGET)
    questions = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: questions.append(args[1]) or QMessageBox.StandardButton.Yes,
    )
    status_items = _fake_status_item(monkeypatch)
    window = MainWindow(settings, **_managers(settings, service))
    resident = FakeResident()
    monkeypatch.setattr(window.speech_settings, "resident", resident)
    cancelled = []
    monkeypatch.setattr(
        window.speech_settings, "cancel", lambda **kwargs: cancelled.append(("check", kwargs))
    )
    monkeypatch.setattr(
        window.speech_settings.microphone_test,
        "cancel",
        lambda **kwargs: cancelled.append(("micro", kwargs)),
    )
    try:
        assert window.setup_tray_icon() is True
        tray = status_items[0]
        assert tray.visibility == [(DICTATION_MENU_ENTRY, False)]
        assert _bound() == {MAIN, CUSTOM}
        saved = _raw(settings)

        window.feature_mode_settings.advanced_check.setChecked(True)
        window.feature_mode_settings.experimental_check.setChecked(True)
        window.app_save_button.click()

        assert settings.get_advanced_features_enabled()
        assert settings.get_experimental_features_enabled()
        assert _features_shown(window) == ALL_SHOWN
        assert window.dictation_behavior.hint.text() == PROMPT_MODEL_HINT
        assert tray.visibility[-1] == (DICTATION_MENU_ENTRY, True)
        assert _bound() == {MAIN, CUSTOM, DICTATION, "<cmd>+<shift>+1"}
        assert window.dictation_hotkey_manager.registered
        # The saved delay applies again.
        assert resident.calls == [("idle", -1)]
        assert not cancelled
        assert dialogs == [
            ("information", "Réglages enregistrés", "Les modifications sont actives.")
        ]
        assert _raw(settings) == saved

        dialogs.clear()
        window.feature_mode_settings.advanced_check.setChecked(False)
        window.feature_mode_settings.experimental_check.setChecked(False)
        window.app_save_button.click()

        # One prompt keeps its own model: confirmed before falling back.
        assert questions == ["Désactiver les fonctions avancées"]
        assert not settings.get_advanced_features_enabled()
        assert not settings.get_experimental_features_enabled()
        assert _features_shown(window) == ALL_HIDDEN
        assert window.dictation_behavior.hint.text() == GENERAL_MODEL_HINT
        assert tray.visibility[-1] == (DICTATION_MENU_ENTRY, False)
        assert _bound() == {MAIN, CUSTOM}
        assert not window.dictation_hotkey_manager.registered
        assert window.dictation_hotkey_manager.last_register_error == ""
        # No idle voice model for a hidden feature; nothing was running, so
        # nothing is cancelled and the voice page keeps its last result.
        assert resident.calls[1:] == [("idle", 0), ("unload",)]
        assert not cancelled
        assert len(dialogs) == 1 and dialogs[0][0] == "information"
        # Nothing was rewritten: everything returns when turned back on.
        assert _raw(settings) == saved
        assert settings.get_speech_idle_seconds() == -1
        prompt = settings.get_prompt(_first_prompt_id(settings))
        assert prompt["hotkey"] == "Cmd+Shift+1"
        assert prompt["model_target"] == OPENAI_TARGET
    finally:
        _close(window)


def test_unchanged_switches_apply_only_the_theme(qt_app, tmp_path, monkeypatch, dialogs):
    window = MainWindow(_new_install(tmp_path, monkeypatch))
    applied = []
    monkeypatch.setattr(window, "apply_feature_modes", lambda *args: applied.append(args))
    try:
        window.app_save_button.click()
        assert applied == []
        assert dialogs == [
            ("information", "Réglages enregistrés", "Les modifications sont actives.")
        ]
    finally:
        _close(window)


class FakeSpeechBackend(SpeechBackend):
    phase = "download"

    def __init__(self):
        super().__init__()
        self.cancelled = False

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True


def test_a_voice_check_stopped_by_the_switch_is_not_shown_running_again(
    qt_app, tmp_path, monkeypatch, dialogs
):
    window = MainWindow(_new_install(tmp_path, monkeypatch, experimental=True))
    speech = window.speech_settings
    monkeypatch.setattr(speech, "resident", FakeResident())
    backend = FakeSpeechBackend()
    speech.backend_factory = lambda _options: backend
    try:
        speech.prepare("download")
        backend.progress.emit("Téléchargement du modèle vocal", 45)
        assert speech.status.title.text() == "Téléchargement du modèle"

        window.feature_mode_settings.experimental_check.setChecked(False)
        window.app_save_button.click()
        assert backend.cancelled and speech.backend is None

        window.feature_mode_settings.experimental_check.setChecked(True)
        window.app_save_button.click()
        # The interrupted operation is reported as such, not as still running.
        assert speech.status.title.text() == "Opération annulée"
        assert speech.status.progress_bar.isHidden()
        assert speech.status.caption.isHidden()
        assert speech.cancel_button.isHidden()
    finally:
        _close(window)


@pytest.mark.parametrize("outcome", ["download", "failure"])
def test_an_idle_voice_page_keeps_its_last_result_across_the_switch(
    qt_app, tmp_path, monkeypatch, dialogs, outcome
):
    window = MainWindow(_new_install(tmp_path, monkeypatch, experimental=True))
    speech = window.speech_settings
    monkeypatch.setattr(speech, "resident", FakeResident())
    backend = FakeSpeechBackend()
    speech.backend_factory = lambda _options: backend
    try:
        speech.prepare("probe")
        if outcome == "download":
            backend.result.emit({"cached": False})
            expected = ("Modèle vocal à télécharger", "Vérifier", True)
        else:
            backend.failed.emit("Moteur absent")
            expected = ("Moteur vocal indisponible", "Réessayer", False)
        assert speech.backend is None

        for experimental in (False, True):
            window.feature_mode_settings.experimental_check.setChecked(experimental)
            window.app_save_button.click()

        # Nothing was running: the page is exactly as the check left it.
        assert (
            speech.status.title.text(),
            speech.check_button.text(),
            speech.download_button.isEnabled(),
        ) == expected
        if outcome == "download":
            assert not speech.download_button.isHidden()
    finally:
        _close(window)


def test_a_voice_model_in_use_unloads_once_experimental_features_are_off(
    qt_app, tmp_path, monkeypatch, dialogs
):
    settings = _new_install(tmp_path, monkeypatch, advanced=True, experimental=True)
    settings.set_speech_idle_seconds(-1)  # « À la fermeture »
    settings.sync()
    window = MainWindow(settings)
    resident = ResidentSpeechService()
    monkeypatch.setattr(resident, "_stop", lambda: setattr(resident, "loaded", False))
    monkeypatch.setattr(window.speech_settings, "resident", resident)
    # A dictation is running with its voice model loaded.
    resident.loaded = True
    resident.active = object()
    resident.idle_seconds = -1
    try:
        window.feature_mode_settings.experimental_check.setChecked(False)
        window.app_save_button.click()
        # The running dictation is not interrupted.
        assert resident.loaded

        resident.active = None
        resident._idle()

        # It ends: nothing keeps the model loaded for a disabled feature.
        assert not resident.loaded
        assert not resident.idle_timer.isActive()
        assert settings.get_speech_idle_seconds() == -1
    finally:
        _close(window)


def test_refusing_to_turn_advanced_off_keeps_prompt_shortcuts_and_models(
    qt_app, tmp_path, monkeypatch, service, dialogs
):
    settings = Settings(config_path=str(tmp_path / "settings.ini"))
    _edit_first_prompt(settings, hotkey="Cmd+Shift+1", model_target=OPENAI_TARGET)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No
    )
    window = MainWindow(settings, **_managers(settings, service))
    try:
        window.feature_mode_settings.advanced_check.setChecked(False)
        window.app_save_button.click()

        assert settings.get_advanced_features_enabled()
        assert window.feature_mode_settings.advanced_check.isChecked()
        assert _features_shown(window) == ALL_SHOWN
        assert "<cmd>+<shift>+1" in _bound()
        assert len(dialogs) == 1 and dialogs[0][0] == "information"
    finally:
        _close(window)


def test_enabling_dictation_keeps_startup_priority_over_a_prompt_shortcut(
    qt_app, tmp_path, monkeypatch, service, dialogs
):
    settings = _new_install(tmp_path, monkeypatch, advanced=True)
    settings.set_dictation_hotkey("Cmd+Shift+D")
    first, second, third = _set_prompt_hotkeys(
        settings, "Cmd+Shift+D", "Cmd+Shift+2"
    )
    managers = _managers(settings, service)
    # Instant dictation is off, so the prompt may use its saved shortcut.
    assert not isinstance(FakeListener.instances[-1].bindings[DICTATION], ReleaseBinding)
    window = MainWindow(settings, **managers)
    name = settings.get_prompt(first)["name"]
    try:
        window.feature_mode_settings.experimental_check.setChecked(True)
        window.app_save_button.click()

        # As after a relaunch: the core shortcut wins over that prompt only.
        assert isinstance(FakeListener.instances[-1].bindings[DICTATION], ReleaseBinding)
        assert window.dictation_hotkey_manager.registered
        assert service.shortcut_owners() == {
            MAIN: "menu principal",
            CUSTOM: "mode personnalisé",
            DICTATION: "dictée instantanée",
            "<cmd>+<shift>+2": "raccourcis des prompts",
        }
        assert window.prompt_hotkey_manager.errors == {
            first: "Ce raccourci est déjà utilisé par dictée instantanée."
        }
        assert len(dialogs) == 1
        kind, title, text = dialogs[0]
        assert (kind, title) == ("warning", "Raccourcis inactifs")
        assert f"- {name} : Ce raccourci est déjà utilisé par dictée instantanée." in text
        assert "Choisissez-en un autre dans Réglages > Raccourcis" in text
        assert settings.get_prompt(first)["hotkey"] == "Cmd+Shift+D"

        # The known conflict never blocks saving a prompt, itself included.
        dialogs.clear()
        for prompt_id in (third, first):
            _select(window, prompt_id)
            window.prompt_instruction.setPlainText(f"Consigne {prompt_id}")
            assert window.save_current_prompt(False) is True
        assert dialogs == []
        assert settings.get_prompt(first)["hotkey"] == "Cmd+Shift+D"
        assert "<cmd>+<shift>+2" in _bound()

        # Clearing the dictation shortcut gives the prompt its own back.
        window.dictation_shortcut_settings.set_shortcut("")
        assert service.shortcut_owners()[DICTATION] == "raccourcis des prompts"
        assert window.prompt_hotkey_manager.errors == {}
    finally:
        _close(window)


def test_a_shortcut_recorded_while_prompt_shortcuts_are_hidden_blocks_nothing(
    qt_app, tmp_path, monkeypatch, service, dialogs
):
    _granted(monkeypatch)
    settings = _new_install(tmp_path, monkeypatch)
    first, second, third = _set_prompt_hotkeys(
        settings, "Cmd+Shift+1", "Cmd+Shift+2"
    )
    name = settings.get_prompt(first)["name"]
    conflict = "Ce raccourci est déjà utilisé par menu principal."
    window = MainWindow(settings, **_managers(settings, service))
    try:
        # Advanced off: the prompt shortcut is hidden and unbound, so the main
        # shortcut may take it.
        window._apply_recorded_hotkey(
            window.hotkey_manager, window.main_hotkey, "Cmd+Shift+1"
        )
        assert settings.get_hotkey() == "Cmd+Shift+1"
        assert dialogs == []

        window.feature_mode_settings.advanced_check.setChecked(True)
        window.app_save_button.click()

        # Only the prompt in conflict stays unbound, and it is named.
        assert service.shortcut_owners() == {
            "<cmd>+<shift>+1": "menu principal",
            CUSTOM: "mode personnalisé",
            "<cmd>+<shift>+2": "raccourcis des prompts",
        }
        assert window.prompt_hotkey_manager.errors == {first: conflict}
        assert len(dialogs) == 1
        kind, title, text = dialogs[0]
        assert (kind, title) == ("warning", "Raccourcis inactifs")
        assert f"- {name} : {conflict}" in text
        # Also named after a relaunch, which then shows the window.
        assert window.refused_hotkey_messages() == [f"« {name} » : {conflict}"]
        window.refresh_permission_status()
        status = window.hotkey_service_status.text()
        assert f"« {name} »" in status and "relance" not in status

        # Saving any prompt still works, the one in conflict included.
        dialogs.clear()
        for prompt_id in (third, first):
            _select(window, prompt_id)
            window.prompt_instruction.setPlainText(f"Consigne {prompt_id}")
            assert window.save_current_prompt(False) is True
        assert dialogs == []
        assert settings.get_prompt(third)["prompt"] == f"Consigne {third}"
        assert settings.get_prompt(first)["hotkey"] == "Cmd+Shift+1"

        # A new conflict is still refused.
        _select(window, third)
        window.prompt_hotkey.setText("Cmd+Shift+1")
        assert window.save_current_prompt(False) is False
        assert [dialog[:2] for dialog in dialogs] == [("warning", "Raccourci invalide")]
        assert settings.get_prompt(third)["hotkey"] == ""

        # Moving the main shortcut gives the prompt its own back at once.
        window._apply_recorded_hotkey(
            window.hotkey_manager, window.main_hotkey, "Cmd+Shift+K"
        )
        assert service.shortcut_owners()["<cmd>+<shift>+1"] == (
            "raccourcis des prompts"
        )
        assert window.prompt_hotkey_manager.errors == {}
    finally:
        _close(window)


def test_status_item_without_entry_visibility_still_starts(
    qt_app, tmp_path, monkeypatch
):
    created = _fake_status_item(monkeypatch, with_entry_visibility=False)
    window = MainWindow(_new_install(tmp_path, monkeypatch))
    try:
        assert window.setup_tray_icon() is True
        assert window.tray_icon is created[0]
        # The entry list never changes; only its visibility does.
        assert [entry and entry[0] for entry in created[0].actions][2] == (
            DICTATION_MENU_ENTRY
        )
    finally:
        _close(window)


def test_native_status_item_hides_one_entry_by_label():
    class Item:
        hidden = None

        def setHidden_(self, hidden):
            self.hidden = hidden

    item = Item()
    holder = SimpleNamespace(_items={DICTATION_MENU_ENTRY: item})
    NativeStatusItem.set_entry_visible(holder, DICTATION_MENU_ENTRY, False)
    assert item.hidden is True
    NativeStatusItem.set_entry_visible(holder, DICTATION_MENU_ENTRY, True)
    assert item.hidden is False
    NativeStatusItem.set_entry_visible(holder, "Entrée inconnue", False)


def test_shortcuts_are_active_without_a_bound_dictation_shortcut(
    qt_app, tmp_path, monkeypatch, service
):
    _granted(monkeypatch)
    settings = _new_install(tmp_path, monkeypatch)
    settings.set_dictation_hotkey("Cmd+Shift+D")
    window = MainWindow(settings, **_managers(settings, service))
    try:
        assert not window.dictation_hotkey_manager.registered
        window.refresh_permission_status()
        assert "✅ Raccourcis globaux actifs" in window.hotkey_service_status.text()
        assert window.refused_hotkey_messages() == []
    finally:
        _close(window)


def test_saving_a_prompt_keeps_its_hidden_shortcut_and_model(
    qt_app, tmp_path, monkeypatch, service
):
    settings = _new_install(tmp_path, monkeypatch)
    # An LM Link device while the Text server is Ollama: invalid if shown.
    assert settings.get_custom_endpoint_type() == "ollama"
    prompt_id = _edit_first_prompt(
        settings, hotkey="Cmd+Shift+1", model_target=LINK_TARGET
    )
    window = MainWindow(settings, **_managers(settings, service))
    try:
        assert window.prompt_list.currentItem().data(Qt.ItemDataRole.UserRole) == prompt_id
        window.prompt_instruction.setPlainText("Nouvelles instructions")
        # A stale value in the hidden field is not saved either.
        window.prompt_hotkey.setText("Cmd+Shift+9")

        assert window.save_current_prompt(False) is True

        prompt = settings.get_prompt(prompt_id)
        assert prompt["prompt"] == "Nouvelles instructions"
        assert prompt["hotkey"] == "Cmd+Shift+1"
        assert prompt["model_target"] == LINK_TARGET
        assert "<cmd>+<shift>+1" not in _bound()
    finally:
        _close(window)


@pytest.mark.parametrize("advanced", [False, True])
def test_import_keeps_hidden_prompt_shortcuts_without_blocking(
    qt_app, tmp_path, monkeypatch, service, dialogs, advanced
):
    settings = _new_install(tmp_path, monkeypatch, advanced=advanced)
    previous = settings.get_prompts()
    base = dict(next(iter(previous.values())))
    library = {
        # Taken by the main menu: refused with the advanced features only.
        "clash": dict(
            base, name="Conflit", hotkey="Cmd+Shift+Space",
            model_target=LINK_TARGET, position=1,
        ),
        "fine": dict(base, name="Valide", hotkey="Cmd+Shift+9", position=2),
    }
    path = tmp_path / "library.json"
    path.write_text(json.dumps({"prompts": library}), encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *_args, **_kwargs: (str(path), "")
    )
    window = MainWindow(settings, **_managers(settings, service))
    try:
        window.import_prompts()

        if advanced:
            # Shown and bound, the conflict cancels the import as before.
            assert [dialog[:2] for dialog in dialogs] == [
                ("warning", "Import impossible")
            ]
            assert settings.get_prompts() == previous
            return
        assert dialogs == [
            ("information", "Import terminé", "2 prompt(s) importé(s).")
        ]
        prompts = settings.get_prompts()
        assert set(prompts) == {"clash", "fine"}
        assert prompts["clash"]["hotkey"] == "Cmd+Shift+Space"
        assert prompts["clash"]["model_target"] == LINK_TARGET
        assert prompts["fine"]["hotkey"] == "Cmd+Shift+9"
        assert _bound() == {MAIN, CUSTOM}
    finally:
        _close(window)


def test_a_failing_apply_step_never_blocks_the_others(
    qt_app, tmp_path, monkeypatch, service, dialogs
):
    settings = _new_install(tmp_path, monkeypatch)
    _edit_first_prompt(settings, hotkey="Cmd+Shift+1")
    window = MainWindow(settings, **_managers(settings, service))

    class BrokenResident(FakeResident):
        def set_idle_seconds(self, seconds):
            raise RuntimeError("service vocal indisponible")

    monkeypatch.setattr(window.speech_settings, "resident", BrokenResident())
    try:
        window.feature_mode_settings.advanced_check.setChecked(True)
        window.app_save_button.click()

        assert settings.get_advanced_features_enabled()
        assert window.text_prompt_form.is_advanced_visible()
        assert "<cmd>+<shift>+1" in _bound()
        assert dialogs == [
            ("information", "Réglages enregistrés", "Les modifications sont actives.")
        ]
    finally:
        _close(window)


@pytest.mark.parametrize("experimental", [False, True])
def test_complete_save_skips_hidden_dictation_settings(
    qt_app, tmp_path, monkeypatch, dialogs, experimental
):
    settings = _new_install(tmp_path, monkeypatch, experimental=experimental)
    window = MainWindow(settings)
    saves = []
    monkeypatch.setattr(window.speech_settings, "save", lambda: saves.append(1) or True)
    try:
        assert window.save_settings() is True
        assert saves == ([1] if experimental else [])
    finally:
        _close(window)


# Shortcuts.


def test_instant_dictation_shortcut_follows_the_experimental_switch(
    qt_app, tmp_path, monkeypatch, service
):
    settings = _new_install(tmp_path, monkeypatch)
    settings.set_dictation_hotkey("Cmd+Shift+D")
    managers = _managers(settings, service)
    dictation = managers["dictation_hotkey_manager"]
    try:
        assert _bound() == {MAIN, CUSTOM}
        assert not dictation.registered
        assert dictation.last_register_error == ""
        assert dictation.refused_hotkey_error == ""
        assert settings.get_dictation_hotkey() == "Cmd+Shift+D"

        settings.set_experimental_features_enabled(True)
        assert dictation.register_hotkey() is True
        assert DICTATION in _bound()
        assert dictation.registered
    finally:
        for manager in managers.values():
            manager.close()


def test_prompt_shortcuts_follow_the_advanced_switch(
    qt_app, tmp_path, monkeypatch, service
):
    settings = _new_install(tmp_path, monkeypatch)
    prompt_id = _edit_first_prompt(settings, hotkey="Cmd+Shift+1")
    managers = _managers(settings, service)
    prompts = managers["prompt_hotkey_manager"]
    try:
        assert prompts.refresh_hotkeys() == (True, {})
        assert _bound() == {MAIN, CUSTOM}
        # A hidden shortcut never blocks saving, even one taken meanwhile.
        candidate = settings.get_prompts()
        candidate[prompt_id]["hotkey"] = "Cmd+Shift+Space"
        assert prompts.validate_prompts(candidate) == (True, {})

        settings.set_advanced_features_enabled(True)
        valid, errors = prompts.validate_prompts(candidate)
        assert not valid and "registration" in errors
        assert prompts.refresh_hotkeys() == (True, {})
        assert "<cmd>+<shift>+1" in _bound()
        assert settings.get_prompt(prompt_id)["hotkey"] == "Cmd+Shift+1"
    finally:
        for manager in managers.values():
            manager.close()


# Prompt menu and requests.


@pytest.mark.parametrize("experimental", [False, True])
def test_voice_submenu_follows_the_experimental_switch(
    qt_app, tmp_path, monkeypatch, experimental
):
    monkeypatch.setattr(context_menu, "activate_current_application", lambda: True)
    monkeypatch.setattr(context_menu, "current_application_is_active", lambda: True)
    settings = _new_install(tmp_path, monkeypatch, experimental=experimental)
    manager = context_menu.ContextMenuManager(settings)
    try:
        manager._present_menu("Sélection", object())
        labels = [action.text() for action in manager._active_menu.actions()]
        assert "Mode personnalisé…" in labels
        assert ("Voix" in labels) is experimental
    finally:
        manager.close()


@pytest.mark.parametrize("advanced", [False, True])
def test_prompt_model_is_used_only_with_the_advanced_features(
    qt_app, tmp_path, monkeypatch, advanced
):
    settings = _new_install(tmp_path, monkeypatch, advanced=advanced)
    prompt_id = _edit_first_prompt(settings, model_target=OPENAI_TARGET)
    manager = context_menu.ContextMenuManager(settings)
    created = []

    def create_client(client_settings=None):
        created.append(client_settings)
        return FakeClient(client_settings)

    monkeypatch.setattr(manager, "_create_api_client", create_client)
    general = []
    monkeypatch.setattr(
        manager.api_client, "send_request", lambda *args, **kwargs: general.append(args)
    )
    try:
        prompt = settings.get_prompt(prompt_id)
        manager._send_request(
            prompt["prompt"], "Texte", model_target=prompt["model_target"]
        )
        if advanced:
            assert len(created) == 1
            assert isinstance(created[0], ModelTargetSettings)
            assert not general
            assert manager.response_window.last_model_target == OPENAI_TARGET
        else:
            assert created == []
            assert len(general) == 1
            assert manager.response_window.last_model_target == {}
        assert settings.get_prompt(prompt_id)["model_target"] == OPENAI_TARGET
    finally:
        manager.close()


def test_hidden_features_ignore_queued_shortcuts_and_menu_requests(
    qt_app, tmp_path, monkeypatch
):
    def fail(*_args, **_kwargs):
        raise AssertionError("Fonction masquée déclenchée")

    settings = _new_install(tmp_path, monkeypatch)
    manager = context_menu.ContextMenuManager(settings)
    monkeypatch.setattr(context_menu.PasteTarget, "capture", fail)
    monkeypatch.setattr(context_menu, "activate_current_application", fail)
    monkeypatch.setattr(manager, "_capture_selection", fail)
    # A dictation started earlier from the menu, still recording.
    session = FakeSession()
    manager._dictation = session
    try:
        manager.start_dictation(from_ui=True)
        manager.start_dictation(target=object())
        manager.start_instant_dictation()
        manager.finish_instant_dictation()
        manager._start_voice_session(fail)
        manager.run_voice_prompt("resumer_vocal", from_ui=True)
        manager.run_prompt_hotkey(_first_prompt_id(settings))

        assert manager._dictation is session
        assert session.calls == []
        assert getattr(manager, "_instant_session", None) is None
    finally:
        manager._dictation = None
        manager.close()


# Local voice model retention.


@pytest.mark.parametrize("advanced, expected", [(False, 300), (True, -1)])
def test_voice_model_retention_follows_the_advanced_switch(
    qt_app, tmp_path, monkeypatch, advanced, expected
):
    helper = tmp_path / "SuperMenuSpeech"
    helper.write_text("")
    monkeypatch.setattr(speech_backend, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(
        speech_backend,
        "platform",
        SimpleNamespace(mac_ver=lambda: ("26.1", ("", "", ""), "")),
    )
    monkeypatch.setattr(speech_backend, "resource_path", lambda *_parts: str(helper))
    settings = _new_install(tmp_path, monkeypatch, advanced=advanced)
    settings.set_speech_idle_seconds(-1)

    backend = speech_backend.create_speech_backend(
        settings, {"provider": "apple", "action": "start"}
    )

    assert backend.idle_seconds == expected
    assert settings.get_speech_idle_seconds() == -1

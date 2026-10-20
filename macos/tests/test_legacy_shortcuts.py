"""Shortcuts saved before the Cmd/Ctrl rule must not break an updated install."""

import json
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from src import main as main_module
from src.config.settings import Settings
from src.main import SuperMenu
from src.ui import main_window as main_window_module
from src.ui.main_window import MainWindow
from src.utils.hotkey_manager import (
    HotkeyManager,
    HotkeyService,
    PromptHotkeyManager,
)
from src.utils.permissions import PermissionStatus


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


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def settings(tmp_path):
    return Settings(config_path=str(tmp_path / "settings.ini"))


@pytest.fixture
def service():
    FakeListener.instances = []
    instance = HotkeyService(listener_factory=FakeListener)
    yield instance
    instance.close()


@pytest.fixture
def warnings(monkeypatch):
    shown = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, message: shown.append((title, message)),
    )
    return shown


def _add_prompts(settings, **hotkeys):
    prompts = settings.get_prompts()
    base = next(iter(prompts.values()))
    for position, (prompt_id, hotkey) in enumerate(hotkeys.items(), start=1):
        prompts[prompt_id] = dict(
            base, name=prompt_id.upper(), hotkey=hotkey, position=position
        )
    settings.set_prompts(prompts)


def _window(settings, service, **managers):
    window = MainWindow(
        settings,
        prompt_hotkey_manager=PromptHotkeyManager(settings, service=service),
        **managers,
    )
    return window


def _select(window, prompt_id):
    for row in range(window.prompt_list.count()):
        item = window.prompt_list.item(row)
        if item.data(Qt.ItemDataRole.UserRole) == prompt_id:
            window.prompt_list.setCurrentItem(item)
            return
    raise AssertionError(prompt_id)


def _close(window):
    window._quitting = True
    window.close()
    window.deleteLater()


def _bound():
    return set(FakeListener.instances[-1].bindings)


def test_legacy_prompt_shortcuts_stay_bound_and_never_block_saving(
    qt_app, settings, service, warnings
):
    # Both accepted by the previous recorder.
    _add_prompts(settings, a="Option+Space", b="Shift+K")
    window = _window(settings, service)
    assert window.prompt_hotkey_manager.errors == {}
    assert {"<alt>+<space>", "<shift>+k"} <= _bound()

    _select(window, "a")
    window.prompt_hotkey.setText("Cmd+Shift+1")
    assert window.save_current_prompt(False) is True

    _select(window, "b")
    window.prompt_hotkey.setText("")
    assert window.save_current_prompt(False) is True

    other = next(
        prompt_id for prompt_id in settings.get_prompts() if prompt_id not in "ab"
    )
    _select(window, other)
    assert window.save_current_prompt(False) is True

    assert warnings == []
    stored = settings.get_prompts()
    assert stored["a"]["hotkey"] == "Cmd+Shift+1"
    assert stored["b"]["hotkey"] == ""
    assert "<cmd>+<shift>+1" in _bound()
    assert "<shift>+k" not in _bound()
    _close(window)


def test_saving_an_unchanged_legacy_shortcut_keeps_it(
    qt_app, settings, service, warnings
):
    _add_prompts(settings, a="Option+Space")
    window = _window(settings, service)

    _select(window, "a")
    window.prompt_instruction.setPlainText("Nouvelle consigne")
    assert window.save_current_prompt(False) is True

    assert warnings == []
    assert settings.get_prompts()["a"]["hotkey"] == "Option+Space"
    assert "<alt>+<space>" in _bound()
    _close(window)


def test_a_new_typing_shortcut_on_a_prompt_is_refused(
    qt_app, settings, service, warnings
):
    _add_prompts(settings, a="Cmd+Shift+1", b="Shift+K")
    window = _window(settings, service)

    _select(window, "a")
    window.prompt_hotkey.setText("Option+K")

    assert window.save_current_prompt(False) is False
    assert len(warnings) == 1
    title, message = warnings[0]
    assert title == "Raccourci invalide"
    assert message.startswith("« A » : ")
    assert "Cmd ou Ctrl" in message
    assert settings.get_prompts()["a"]["hotkey"] == "Cmd+Shift+1"
    _close(window)


def test_a_conflict_with_an_unchanged_prompt_names_the_edited_one(
    qt_app, settings, service, warnings
):
    _add_prompts(settings, a="Cmd+Shift+1", b="Shift+K")
    window = _window(settings, service)

    _select(window, "b")
    window.prompt_hotkey.setText("Cmd+Shift+1")

    assert window.save_current_prompt(False) is False
    assert warnings == [
        (
            "Raccourci invalide",
            "« B » : Ce raccourci est déjà utilisé par un autre prompt.",
        )
    ]
    assert settings.get_prompts()["b"]["hotkey"] == "Shift+K"
    _close(window)


def test_import_keeps_legacy_shortcuts_and_reports_refused_ones(
    qt_app, settings, service, warnings, tmp_path, monkeypatch
):
    window = _window(settings, service)
    prompts = settings.get_prompts()
    base = next(iter(prompts.values()))
    library = {
        # A Windows library: Alt+Shift+X was accepted by the previous import.
        "windows": dict(base, name="Windows", hotkey="Alt+Shift+X", position=1),
        "copy": dict(base, name="Copie", hotkey="Cmd+C", position=2),
        "fine": dict(base, name="Valide", hotkey="Cmd+Shift+9", position=3),
    }
    path = tmp_path / "library.json"
    path.write_text(json.dumps({"prompts": library}), encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *_args, **_kwargs: (str(path), "")
    )
    information = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, message: information.append((title, message)),
    )

    window.import_prompts()

    assert warnings == []
    assert set(settings.get_prompts()) == {"windows", "copy", "fine"}
    assert {"<alt>+<shift>+x", "<cmd>+<shift>+9"} <= _bound()
    assert "<cmd>+c" not in _bound()
    (title, message), = information
    assert title == "Import terminé"
    assert "3 prompt(s) importé(s)." in message
    assert "« Copie » : " in message
    assert "Définir" in message
    _close(window)


def test_import_conflicting_with_the_main_shortcut_is_still_cancelled(
    qt_app, settings, service, warnings, tmp_path, monkeypatch
):
    main_manager = HotkeyManager(settings, service=service)
    window = _window(settings, service, hotkey_manager=main_manager)
    previous = settings.get_prompts()
    base = next(iter(previous.values()))
    library = {
        "clash": dict(base, name="Doublon", hotkey=settings.get_hotkey()),
    }
    path = tmp_path / "library.json"
    path.write_text(json.dumps({"prompts": library}), encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *_args, **_kwargs: (str(path), "")
    )

    window.import_prompts()

    assert warnings and warnings[0][0] == "Import impossible"
    assert settings.get_prompts() == previous
    _close(window)


def _granted(monkeypatch):
    monkeypatch.setattr(
        main_window_module,
        "current_permission_status",
        lambda: PermissionStatus(accessibility=True),
    )


def test_legacy_dictation_shortcut_still_starts_without_warning(
    qt_app, settings, service, monkeypatch
):
    _granted(monkeypatch)
    settings.set_dictation_hotkey("Option+Space")
    managers = {
        "hotkey_manager": HotkeyManager(settings, service=service),
        "custom_hotkey_manager": HotkeyManager(
            settings, custom_hotkey=True, service=service
        ),
        "dictation_hotkey_manager": HotkeyManager(
            settings, dictation_hotkey=True, service=service
        ),
    }
    window = _window(settings, service, **managers)

    assert "<alt>+<space>" in _bound()
    assert window.refused_hotkey_messages() == []
    window.refresh_permission_status()
    assert "✅ Raccourcis globaux actifs" in window.hotkey_service_status.text()
    _close(window)


def test_refused_saved_shortcut_asks_to_record_it_again(
    qt_app, settings, service, monkeypatch
):
    _granted(monkeypatch)
    settings.set_custom_hotkey("Cmd+V")
    _add_prompts(settings, a="Cmd+Z")
    managers = {
        "hotkey_manager": HotkeyManager(settings, service=service),
        "custom_hotkey_manager": HotkeyManager(
            settings, custom_hotkey=True, service=service
        ),
    }
    window = _window(settings, service, **managers)

    messages = window.refused_hotkey_messages()
    assert messages[0].startswith("Mode personnalisé : ")
    assert messages[1].startswith("« A » : ")

    window.refresh_permission_status()
    status = window.hotkey_service_status.text()
    assert "Mode personnalisé" in status
    assert "Définir" in status
    # Relaunching would refuse the same saved value again.
    assert "relance" not in status
    _close(window)


def test_service_failure_still_suggests_relaunching(
    qt_app, settings, service, monkeypatch
):
    _granted(monkeypatch)
    managers = {
        "hotkey_manager": HotkeyManager(settings, service=service),
        "custom_hotkey_manager": HotkeyManager(
            settings, custom_hotkey=True, service=service
        ),
    }
    window = _window(settings, service, **managers)
    service.close()
    monkeypatch.setattr(service, "restart", lambda: False)
    window._reload_all_hotkeys()

    assert window.refused_hotkey_messages() == []
    window.refresh_permission_status()
    assert "relance" in window.hotkey_service_status.text()
    _close(window)


class _StartupWindow:
    def __init__(self, refused):
        self.refused = refused
        self.calls = []

    def setup_tray_icon(self):
        return True

    def refused_hotkey_messages(self):
        return self.refused

    def show_permission_setup(self):
        self.calls.append("setup")

    def show_main_window(self):
        self.calls.append("show")

    def hide(self):
        self.calls.append("hide")

    def schedule_startup_update_check(self):
        self.calls.append("update")


@pytest.mark.parametrize(
    "refused,expected",
    [
        (["Menu principal : Ce raccourci est réservé"], ["setup", "update"]),
        ([], ["hide", "update"]),
    ],
)
def test_startup_opens_the_configuration_when_a_shortcut_is_refused(
    monkeypatch, refused, expected
):
    monkeypatch.setattr(main_module, "accessibility_is_trusted", lambda: True)
    window = _StartupWindow(refused)

    SuperMenu._finish_startup(SimpleNamespace(main_window=window))

    assert window.calls == expected


def test_a_brand_new_installation_opens_the_engine_settings(monkeypatch):
    monkeypatch.setattr(main_module, "accessibility_is_trusted", lambda: True)
    window = _StartupWindow([])
    opened = []
    window.show_settings_page = opened.append

    SuperMenu._finish_startup(
        SimpleNamespace(main_window=window, settings=SimpleNamespace(first_launch=True))
    )

    assert opened == ["text"]
    assert "hide" not in window.calls

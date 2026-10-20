"""A brand-new installation is welcomed; the capture mode saves itself."""

from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from src import main
from src.ui.main_window_settings import SettingsPageMixin


class _Window:
    def __init__(self, tray=True):
        self.calls = []
        self.tray_icon = SimpleNamespace(showMessage=self._message) if tray else None
        self.messages = []

    def _message(self, title, text, *_args):
        self.messages.append((title, text))

    def show_settings_page(self, key):
        self.calls.append(("settings", key))

    def hide(self):
        self.calls.append("hide")


def _app(first_launch, window):
    settings = SimpleNamespace(first_launch=first_launch, get_hotkey=lambda: "Ctrl+²")
    return SimpleNamespace(settings=settings, main_window=window)


def test_first_launch_opens_the_engine_settings_and_names_the_shortcut():
    window = _Window()
    main.SuperMenu._show_hidden_or_welcome(_app(True, window))

    assert window.calls == [("settings", "text")]
    assert window.messages[0][0] == "SuperMenu est prêt"
    assert "Ctrl+²" in window.messages[0][1]


def test_later_launches_start_hidden_in_the_notification_area():
    window = _Window()
    main.SuperMenu._show_hidden_or_welcome(_app(False, window))

    assert window.calls == ["hide"]
    assert window.messages == []


def test_first_launch_without_notification_area_still_opens_the_settings():
    window = _Window(tray=False)
    main.SuperMenu._show_hidden_or_welcome(_app(True, window))

    assert window.calls == [("settings", "text")]


def test_choosing_a_capture_mode_saves_it_at_once():
    QApplication.instance() or QApplication([])
    from supermenu_core.ui.controls import ChoiceBox

    saved = []
    combo = ChoiceBox()
    for label, mode in (("Plein écran", "fullscreen"), ("Sélection de zone", "region")):
        combo.addItem(label, mode)
    settings = SimpleNamespace(
        get_screenshot_capture_mode=lambda: saved[-1] if saved else "fullscreen",
        set_screenshot_capture_mode=saved.append,
    )
    owner = SimpleNamespace(screenshot_capture_mode_combo=combo, settings=settings)
    combo.currentIndexChanged.connect(
        lambda *_: SettingsPageMixin.save_screenshot_capture_mode(owner)
    )

    combo.setCurrentIndex(1)
    combo.setCurrentIndex(1)

    assert saved == ["region"]

"""Regressions for the macOS stability fixes: stuck states and lost content."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QMessageBox

from src.config.settings import Settings
from src.ui.main_window import MainWindow
from src.utils import context_menu as context_menu_module
from src.utils import system_version
from src.utils.clipboard_manager import ClipboardManager
from src.utils.context_menu import ContextMenuManager
from src.utils.hotkey_manager import (
    HotkeyRecorderDialog,
    _MacOSGlobalHotKeys,
    normalize_hotkey,
)
from src.utils.key_events import KeyEventPoster
from src.utils.selection import SelectionReader
from src.utils.text_inserter import TextInserter
from supermenu_core.ui.dictation_dialog import RecordingDialog

from tests.fake_key_api import FakeQuartzKeyAPI
from tests.test_hotkeys import FakeAppKitEventAPI, FakeAppKitKeyEvent
from tests.test_selection import FakeAccessibility, FakeTarget, QueuedScheduler


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def manager(qt_app, tmp_path):
    value = ContextMenuManager(Settings(str(tmp_path / "settings.ini")))
    yield value
    value.close()


# Clipboard ---------------------------------------------------------------


def test_copied_image_survives_the_clipboard_round_trip(qt_app):
    image = QImage(4, 3, QImage.Format.Format_ARGB32)
    image.fill(QColor("red"))
    qt_app.clipboard().setImage(image)

    snapshot = ClipboardManager.capture_snapshot()
    # SuperMenu borrows the clipboard for its own Command+C / Command+V...
    qt_app.clipboard().setText("réponse à coller")
    assert ClipboardManager.restore_if_unchanged(snapshot, "réponse à coller")

    # ...and the user's image comes back readable, not as an empty entry.
    restored = qt_app.clipboard().image()
    assert not restored.isNull()
    assert (restored.width(), restored.height()) == (4, 3)
    assert restored.pixelColor(0, 0) == QColor("red")


def test_text_snapshot_is_still_restored_as_text(qt_app):
    qt_app.clipboard().setText("texte de l’utilisateur")

    snapshot = ClipboardManager.capture_snapshot()
    qt_app.clipboard().setText("sentinelle")
    assert ClipboardManager.restore_if_unchanged(snapshot, "sentinelle")

    assert snapshot.image is None
    assert qt_app.clipboard().text() == "texte de l’utilisateur"


class BrokenClipboard:
    def capture_snapshot(self):
        raise RuntimeError("presse-papiers verrouillé")

    def set_clipboard_text_safe(self, _text):
        return True

    def get_clipboard_text_safe(self):
        return ""

    def restore_if_unchanged(self, *_args):
        return False


def test_selection_read_ends_when_the_clipboard_step_raises():
    scheduler = QueuedScheduler()
    results = []
    reader = SelectionReader(
        keys=KeyEventPoster(api=FakeQuartzKeyAPI()),
        scheduler=scheduler,
        clipboard=BrokenClipboard(),
        accessibility=FakeAccessibility(None),
    )

    reader.read_async(FakeTarget(active=True), results.append)
    scheduler.drain()

    # The caller is answered: no selection, instead of waiting forever.
    assert results == [""]


def test_insertion_ends_when_the_clipboard_step_raises(monkeypatch):
    scheduler = QueuedScheduler()
    monkeypatch.setattr(
        ClipboardManager,
        "capture_snapshot",
        staticmethod(lambda: (_ for _ in ()).throw(RuntimeError("verrouillé"))),
    )
    results = []
    inserter = TextInserter(
        keys=KeyEventPoster(api=FakeQuartzKeyAPI()), scheduler=scheduler
    )

    inserter.insert_text_async(
        "Texte", FakeTarget(active=True), lambda ok, reason=None: results.append((ok, reason))
    )
    scheduler.drain()

    assert results == [(False, "clipboard_failed")]


# Menu state --------------------------------------------------------------


def test_stale_menu_flag_no_longer_blocks_the_shortcut(manager, monkeypatch):
    captured = []
    monkeypatch.setattr(
        manager, "_capture_selection", lambda on_ready, **_kw: captured.append(on_ready)
    )
    # A menu flag left behind by a missed signal: no menu exists any more.
    manager._menu_open = True
    manager._active_menu = None

    manager.show_menu()

    assert manager._menu_open is False
    assert len(captured) == 1


def test_a_menu_waiting_to_be_shown_is_not_treated_as_stale(manager, monkeypatch):
    monkeypatch.setattr(
        context_menu_module, "activate_current_application", lambda *a, **k: True
    )
    captured = []
    monkeypatch.setattr(
        manager, "_capture_selection", lambda on_ready, **_kw: captured.append(on_ready)
    )
    manager._present_menu("texte", None)
    assert manager._menu_open is True and manager._menu_presentation_pending is True

    manager.show_menu()

    # Still the same pending menu: the second press is ignored, not doubled.
    assert captured == []
    assert manager._menu_open is True


def test_menu_that_cannot_be_built_releases_the_shortcut(manager, monkeypatch):
    def broken(*_args, **_kwargs):
        raise RuntimeError("bibliothèque illisible")

    monkeypatch.setattr(context_menu_module, "populate_prompt_menu", broken)

    with pytest.raises(RuntimeError):
        manager._present_menu("texte", None)

    assert manager._menu_open is False
    assert manager._active_menu is None


# Dictation ---------------------------------------------------------------


def test_dictation_window_stays_visible_when_supermenu_is_deactivated(qt_app):
    dialog = RecordingDialog()
    try:
        # Without it AppKit hides this panel as soon as the user clicks back
        # into the document, while the microphone keeps recording.
        assert dialog.testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
    finally:
        dialog.deleteLater()


def test_failed_dictation_start_does_not_keep_a_deleted_session(manager, monkeypatch):
    class OldSession:
        cleaned = deleted = False

        def cleanup(self):
            self.cleaned = True

        def deleteLater(self):
            self.deleted = True

    old = OldSession()
    manager._dictation = old
    monkeypatch.setattr(
        "supermenu_core.audio.settings.speech_options",
        lambda _settings: (_ for _ in ()).throw(ValueError("Langue invalide")),
    )
    shown = []
    monkeypatch.setattr(
        context_menu_module.SafeDialogs,
        "show_information",
        lambda title, text: shown.append(text),
    )

    manager.start_dictation(target=FakeTarget(active=True))

    assert old.cleaned and old.deleted
    assert manager._dictation is None
    assert shown == ["Langue invalide"]


# Shortcuts ---------------------------------------------------------------


@pytest.mark.parametrize("key", ["F21", "F24"])
def test_function_keys_macos_cannot_bind_are_refused_when_recorded(key):
    normalized, error = normalize_hotkey(f"Shift+{key}")

    assert normalized is None
    assert "non supportée" in error


def test_f20_is_still_accepted():
    assert normalize_hotkey("Shift+F20") == ("<shift>+<f20>", "")


def test_recorder_does_not_offer_f21(qt_app):
    dialog = HotkeyRecorderDialog()
    try:
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent

        dialog.keyPressEvent(
            QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_F21,
                Qt.KeyboardModifier.ShiftModifier,
            )
        )
        assert not dialog.recorded_hotkey
        assert not dialog.ok_button.isEnabled()
    finally:
        dialog.deleteLater()


class LayoutSwitchingKeyEvent(FakeAppKitKeyEvent):
    """A layout that types Latin letters only while Command is held."""

    def __init__(self, *, typed, **kwargs):
        super().__init__(**kwargs)
        self._typed = typed

    def characters(self):
        return self._typed


def test_shortcut_fires_on_layouts_that_switch_to_latin_under_command():
    api = FakeAppKitEventAPI()
    listener = _MacOSGlobalHotKeys(event_api=api)
    triggered = []
    listener.replace_bindings({"<cmd>+<shift>+k": lambda: triggered.append(True)})
    listener.start()

    # Russian layout: the key is "л", but Cmd+Shift types "K".
    api.global_handler(
        LayoutSwitchingKeyEvent(flags=9, key_code=0x28, characters="л", typed="K")
    )
    assert triggered == [True]

    # A key that really is another letter still does nothing.
    api.global_handler(
        LayoutSwitchingKeyEvent(flags=9, key_code=0x25, characters="д", typed="L")
    )
    assert triggered == [True]
    listener.stop()


def test_recorder_resumes_the_shortcuts_even_when_applying_fails(
    qt_app, tmp_path, monkeypatch
):
    class Service:
        def __init__(self):
            self.calls = []

        def suspend(self):
            self.calls.append("suspend")

        def resume(self):
            self.calls.append("resume")

    class Manager:
        def __init__(self, service):
            self.service = service

    class Keys:
        def when_modifiers_released(self, _schedule, callback):
            callback()

    dialogs = []

    class Dialog:
        DialogCode = HotkeyRecorderDialog.DialogCode
        recorded_hotkey = "Cmd+Shift+K"

        def __init__(self, _parent):
            self.finished = self
            dialogs.append(self)

        def connect(self, callback):
            self.callback = callback

        def setWindowModality(self, _modality):
            pass

        def open(self):
            pass

        def deleteLater(self):
            self.deleted = True

    from src.ui import main_window_hotkeys

    monkeypatch.setattr(main_window_hotkeys, "HotkeyRecorderDialog", Dialog)
    window = MainWindow(Settings(str(tmp_path / "settings.ini")))
    try:
        service = Service()
        window.hotkey_manager = Manager(service)
        window._keys = Keys()

        def failing(_hotkey):
            raise RuntimeError("enregistrement impossible")

        recorder = next(
            getattr(window, name)
            for name in ("_record_hotkey", "_open_hotkey_recorder", "record_hotkey")
            if hasattr(window, name)
        )
        recorder(failing)
        with pytest.raises(RuntimeError):
            dialogs[0].callback(Dialog.DialogCode.Accepted)

        assert service.calls == ["suspend", "resume"]
        assert dialogs[0].deleted is True
    finally:
        window._quitting = True
        window.close()
        window.deleteLater()


# Window and updates ------------------------------------------------------


def test_opening_supermenu_restores_a_minimized_window(qt_app, tmp_path):
    window = MainWindow(Settings(str(tmp_path / "settings.ini")))
    try:
        window.showMinimized()
        assert window.isMinimized()

        window.show_main_window()

        assert not window.isMinimized()
        assert window.isVisible()
    finally:
        window._quitting = True
        window.close()
        window.deleteLater()


def test_update_notice_brings_supermenu_forward_before_asking(
    qt_app, tmp_path, monkeypatch
):
    from src.ui import main_window_updates

    window = MainWindow(Settings(str(tmp_path / "settings.ini")))
    order = []
    monkeypatch.setattr(window, "show_main_window", lambda: order.append("forward"))
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args: order.append("question") or QMessageBox.StandardButton.No,
    )
    monkeypatch.setattr(
        main_window_updates.app_updater, "is_newer_version", lambda *_args: True
    )
    try:
        # Found by the silent check at startup, with no window on screen.
        window._update_finished({"version": "9.9.9", "url": ""}, True)

        assert order == ["forward", "question"]
    finally:
        window._quitting = True
        window.close()
        window.deleteLater()


# macOS version -----------------------------------------------------------


@pytest.mark.parametrize(
    ("sw_vers", "mac_ver", "expected"),
    [
        (26, "16.0", 26),  # Compatibility version shown to an older SDK.
        (26, "26.1", 26),
        (15, "15.7", 15),
        (0, "26.0", 26),  # sw_vers unreadable: platform.mac_ver() decides.
        (0, "", 0),
    ],
)
def test_macos_version_is_not_lowered_by_the_compatibility_mode(
    monkeypatch, sw_vers, mac_ver, expected
):
    monkeypatch.setattr(system_version, "_sw_vers_major", sw_vers)
    monkeypatch.setattr(
        system_version.platform, "mac_ver", lambda: (mac_ver, ("", "", ""), "")
    )

    assert system_version.macos_major_version() == expected


def test_sw_vers_is_read_once(monkeypatch):
    calls = []
    monkeypatch.setattr(system_version, "_sw_vers_major", None)
    monkeypatch.setattr(
        system_version, "_read_sw_vers_major", lambda: calls.append(1) or 26
    )

    assert system_version.macos_major_version() == 26
    assert system_version.macos_major_version() == 26
    assert calls == [1]

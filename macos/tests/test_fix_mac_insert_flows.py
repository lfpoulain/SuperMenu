"""Regression tests: request errors, focus after a direct prompt, clipboard."""

import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from src.config.settings import Settings
from src.utils import clipboard_manager
import src.utils.context_menu as context_menu_module
from src.utils.clipboard_manager import ClipboardManager
from src.utils.context_menu import ContextMenuManager


@pytest.fixture
def manager(tmp_path):
    QApplication.instance() or QApplication([])
    value = ContextMenuManager(Settings(config_path=str(tmp_path / "settings.ini")))
    yield value
    value.close()


class FakeResponseWindow:
    def __init__(self):
        self.responses = []
        self.errors = []

    def set_response(self, text):
        self.responses.append(text)

    def set_error(self, text):
        self.errors.append(text)

    def set_loading(self, _loading):
        pass

    def close(self):
        pass


def _record_dialogs(monkeypatch):
    shown = []
    monkeypatch.setattr(
        context_menu_module.SafeDialogs,
        "show_critical",
        lambda title, message, parent=None, **_kwargs: shown.append((title, message)),
    )
    return shown


def _pending(manager, request_id, *, direct):
    manager._pending_requests[request_id] = {
        "client": manager.api_client,
        "insert_directly": direct,
        "target": None,
        "indicator": None,
    }


# --- A superseded request fails silently, as on the other platform --------


def test_the_late_error_of_a_replaced_request_opens_no_dialog(manager, monkeypatch):
    shown = _record_dialogs(monkeypatch)
    manager.response_window.close()
    manager.response_window = FakeResponseWindow()
    _pending(manager, "ancienne", direct=False)
    _pending(manager, "récente", direct=False)
    manager._active_response_request_id = "récente"

    manager.on_request_error_scoped("ancienne", "délai dépassé")

    assert shown == []
    assert manager.response_window.responses == []
    assert "ancienne" not in manager._pending_requests
    assert "récente" in manager._pending_requests


def test_the_active_request_error_still_reaches_the_response_window(
    manager, monkeypatch
):
    shown = _record_dialogs(monkeypatch)
    manager.response_window.close()
    manager.response_window = FakeResponseWindow()
    _pending(manager, "active", direct=False)
    manager._active_response_request_id = "active"

    manager.on_request_error_scoped("active", "délai dépassé")

    assert shown == []
    # Shown as a failure that cannot be inserted, not as an answer.
    assert manager.response_window.errors == ["Erreur : délai dépassé"]
    assert manager.response_window.responses == []


def test_a_direct_request_error_is_still_reported(manager, monkeypatch):
    shown = _record_dialogs(monkeypatch)
    _pending(manager, "directe", direct=True)
    manager._active_response_request_id = "autre"

    manager.on_request_error_scoped("directe", "délai dépassé")

    assert shown == [("Erreur de traitement", "délai dépassé")]


# --- A direct prompt hands the foreground back to the target --------------


class FakeSignal:
    def __init__(self):
        self.callback = None

    def connect(self, callback):
        self.callback = callback

    def emit(self, *args):
        if self.callback is not None:
            self.callback(*args)


class FakeAction:
    def __init__(self, label):
        self.label = label
        self._data = None

    def setEnabled(self, _enabled):
        pass

    def setData(self, data):
        self._data = data

    def data(self):
        return self._data


class FakeMenu:
    instances = []

    def __init__(self):
        self.triggered = FakeSignal()
        self.aboutToShow = FakeSignal()
        self.aboutToHide = FakeSignal()
        self.actions = []
        FakeMenu.instances.append(self)

    def addAction(self, label):
        action = FakeAction(label)
        self.actions.append(action)
        return action

    def addMenu(self, _label):
        return FakeMenu()

    def addSeparator(self):
        pass

    def popup(self, _position):
        pass

    def raise_(self):
        pass

    def isVisible(self):
        return True

    def deleteLater(self):
        pass


class ImmediateTimer:
    @staticmethod
    def singleShot(_delay, callback):
        callback()


def _open_menu(manager, monkeypatch):
    events = []

    class FakeTarget:
        def request_activation(self, force=False):
            events.append("restore_target")
            return True

    class ImmediateSelectionReader:
        @staticmethod
        def read_async(_target, on_finished):
            on_finished("texte sélectionné")

    FakeMenu.instances = []
    monkeypatch.setattr(context_menu_module, "QMenu", FakeMenu)
    monkeypatch.setattr(context_menu_module, "QTimer", ImmediateTimer)
    monkeypatch.setattr(
        context_menu_module.PasteTarget,
        "capture",
        lambda **_kwargs: FakeTarget(),
    )
    monkeypatch.setattr(
        context_menu_module,
        "activate_current_application",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        context_menu_module,
        "current_application_is_active",
        lambda: True,
    )
    monkeypatch.setattr(
        manager,
        "_send_request",
        lambda *args, **kwargs: events.append(
            ("send", kwargs.get("insert_directly", False))
        ),
    )
    monkeypatch.setattr(
        manager,
        "_prepare_response_window",
        lambda *args: events.append("response_window"),
    )
    manager.selection_reader = ImmediateSelectionReader()
    manager.show_menu()
    menu = FakeMenu.instances[0]
    return menu, events


def _choose(menu, label):
    action = next(action for action in menu.actions if action.label == label)
    menu.triggered.emit(action)


def test_a_direct_prompt_returns_focus_to_the_target_during_the_call(
    manager, monkeypatch
):
    manager.settings.add_prompt(
        "direct_test", "Directe", "Corrige", "Correction", insert_directly=True
    )
    menu, events = _open_menu(manager, monkeypatch)

    _choose(menu, "Directe")

    assert ("send", True) in events
    assert "restore_target" in events
    assert manager._menu_open is False


def test_a_prompt_with_a_response_window_keeps_supermenu_in_front(
    manager, monkeypatch
):
    manager.settings.add_prompt(
        "window_test", "Fenêtre", "Résume", "Résumé", insert_directly=False
    )
    menu, events = _open_menu(manager, monkeypatch)

    _choose(menu, "Fenêtre")

    assert "response_window" in events
    assert ("send", False) in events
    assert "restore_target" not in events


def test_unknown_menu_data_is_not_treated_as_a_direct_prompt(manager):
    assert manager._prompt_inserts_directly(None) is False
    assert manager._prompt_inserts_directly(("custom", None)) is False
    assert manager._prompt_inserts_directly(("prompt", "absent")) is False


# --- Internal clipboard writes carry the transient markers ----------------


class FakeQtClipboard:
    """The general pasteboard as Qt sees it."""

    def __init__(self):
        self.value = ""
        self.qt_writes = []

    def text(self):
        return self.value

    def setText(self, text):
        self.qt_writes.append(text)
        self.value = text


class FakePasteboard:
    def __init__(self, qt_clipboard, *, accept_string=True, visible_to_qt=True):
        self.calls = []
        self.qt_clipboard = qt_clipboard
        self.accept_string = accept_string
        self.visible_to_qt = visible_to_qt

    def prepareForNewContentsWithOptions_(self, options):
        self.calls.append(("prepare", options))
        return 1

    def clearContents(self):
        self.calls.append(("clear",))
        return 1

    def setString_forType_(self, text, kind):
        self.calls.append(("string", text, kind))
        if self.accept_string and self.visible_to_qt:
            self.qt_clipboard.value = text
        return self.accept_string

    def setData_forType_(self, data, kind):
        self.calls.append(("data", kind))
        return True


def _clipboards(monkeypatch, *, host_only=1, **pasteboard_options):
    qt_clipboard = FakeQtClipboard()
    pasteboard = FakePasteboard(qt_clipboard, **pasteboard_options)
    thread = QThread.currentThread()
    app = type(
        "FakeApp",
        (),
        {
            "thread": staticmethod(lambda: thread),
            "clipboard": staticmethod(lambda: qt_clipboard),
        },
    )()
    monkeypatch.setattr(
        clipboard_manager,
        "QApplication",
        type("FakeQApplication", (), {"instance": staticmethod(lambda: app)}),
    )
    monkeypatch.setattr(
        clipboard_manager,
        "NSPasteboard",
        type(
            "FakeNSPasteboard",
            (),
            {"generalPasteboard": staticmethod(lambda: pasteboard)},
        ),
    )
    monkeypatch.setattr(
        clipboard_manager,
        "NSPasteboardContentsCurrentHostOnly",
        host_only,
    )
    monkeypatch.setattr(clipboard_manager, "NSData", None)
    return pasteboard, qt_clipboard


def test_internal_writes_are_marked_transient_and_local(monkeypatch):
    pasteboard, qt_clipboard = _clipboards(monkeypatch)

    assert ClipboardManager.set_clipboard_text_safe("réponse") is True

    assert pasteboard.calls[0] == ("prepare", 1)
    assert pasteboard.calls[1] == (
        "string",
        "réponse",
        clipboard_manager.NSPasteboardTypeString,
    )
    marked = {call[1] for call in pasteboard.calls if call[0] == "data"}
    assert marked == {
        "org.nspasteboard.TransientType",
        "org.nspasteboard.ConcealedType",
        "org.nspasteboard.AutoGeneratedType",
    }
    # The marked native value is kept: Qt does not overwrite it.
    assert qt_clipboard.qt_writes == []
    assert ClipboardManager.get_clipboard_text_safe() == "réponse"


def test_older_appkit_clears_the_pasteboard_instead(monkeypatch):
    pasteboard, qt_clipboard = _clipboards(monkeypatch, host_only=None)

    assert ClipboardManager.set_clipboard_text_safe("sentinelle") is True
    assert pasteboard.calls[0] == ("clear",)
    assert qt_clipboard.qt_writes == []


def test_a_refused_native_write_falls_back_to_qt(monkeypatch):
    _pasteboard, qt_clipboard = _clipboards(monkeypatch, accept_string=False)

    assert ClipboardManager.set_clipboard_text_safe("repli Qt") is True
    assert qt_clipboard.qt_writes == ["repli Qt"]


def test_a_native_write_qt_cannot_read_back_falls_back_to_qt(monkeypatch):
    """The sentinel check and the restore compare what Qt reads."""
    _pasteboard, qt_clipboard = _clipboards(monkeypatch, visible_to_qt=False)

    assert ClipboardManager.set_clipboard_text_safe("sentinelle") is True
    assert qt_clipboard.qt_writes == ["sentinelle"]
    assert ClipboardManager.get_clipboard_text_safe() == "sentinelle"


def test_without_appkit_the_qt_clipboard_is_used(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(clipboard_manager, "NSPasteboard", None)

    assert ClipboardManager.set_clipboard_text_safe("texte Qt") is True
    assert app.clipboard().text() == "texte Qt"

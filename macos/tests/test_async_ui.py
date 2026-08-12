from PySide6.QtWidgets import QApplication

from src.config.settings import Settings
import src.utils.context_menu as context_menu_module
from src.utils.context_menu import ContextMenuManager


def test_custom_prompt_dialog_completes_asynchronously(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    manager = ContextMenuManager(
        Settings(config_path=str(tmp_path / "settings.ini"))
    )
    calls = []
    monkeypatch.setattr(
        manager,
        "_prepare_response_window",
        lambda status, prompt, content, target: calls.append(
            ("prepare", status, prompt, content, target)
        ),
    )
    monkeypatch.setattr(
        manager,
        "_send_request",
        lambda prompt, content, target=None: calls.append(
            ("send", prompt, content, target)
        ),
    )
    target = object()

    manager._handle_custom("texte sélectionné", target)
    dialog = manager._prompt_dialog

    assert dialog is not None
    dialog.prompt_input.setPlainText("Reformule")
    dialog.accept_prompt()
    app.processEvents()

    assert manager._prompt_dialog is None
    assert any(call[0] == "prepare" for call in calls)
    assert ("send", "Reformule", "texte sélectionné", target) in calls
    manager.close()


def test_context_menu_activates_supermenu_before_popup(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    manager = ContextMenuManager(
        Settings(config_path=str(tmp_path / "settings.ini"))
    )
    events = []

    class FakeSignal:
        def __init__(self):
            self.callback = None

        def connect(self, callback):
            self.callback = callback

        def emit(self, *args):
            if self.callback is not None:
                self.callback(*args)

    class FakeAction:
        def __init__(self):
            self._data = None

        def setEnabled(self, _enabled):
            pass

        def setData(self, data):
            self._data = data

        def data(self):
            return self._data

    class FakeWindowHandle:
        def requestActivate(self):
            events.append("request_activate")

    class FakeMenu:
        def __init__(self):
            self.triggered = FakeSignal()
            self.aboutToShow = FakeSignal()
            self.aboutToHide = FakeSignal()
            self.visible = False

        def addAction(self, _label):
            return FakeAction()

        def addSeparator(self):
            pass

        def popup(self, _position):
            events.append("popup")
            self.visible = True
            self.aboutToShow.emit()

        def activateWindow(self):
            events.append("activate_window")

        def raise_(self):
            events.append("raise")

        def windowHandle(self):
            return FakeWindowHandle()

        def isVisible(self):
            return self.visible

        def deleteLater(self):
            pass

    class ImmediateTimer:
        @staticmethod
        def singleShot(_delay, callback):
            callback()

    class FakeTarget:
        def activate_and_verify(self):
            events.append("restore_target")
            return True

    monkeypatch.setattr(context_menu_module, "QMenu", FakeMenu)
    monkeypatch.setattr(context_menu_module, "QTimer", ImmediateTimer)
    monkeypatch.setattr(
        context_menu_module.PasteTarget,
        "capture",
        lambda: FakeTarget(),
    )
    monkeypatch.setattr(
        context_menu_module,
        "activate_current_application",
        lambda: events.append("activate_app") or True,
    )
    monkeypatch.setattr(
        context_menu_module,
        "current_application_is_active",
        lambda: True,
    )
    monkeypatch.setattr(manager, "_try_get_selected_text", lambda _target: "")

    manager.show_menu()

    assert events[0:2] == ["activate_app", "popup"]
    assert "request_activate" in events
    assert manager._menu_open is True

    manager._active_menu.aboutToHide.emit()
    assert manager._menu_open is False
    assert events[-1] == "restore_target"
    manager.close()

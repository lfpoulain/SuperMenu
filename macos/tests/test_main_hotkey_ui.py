from types import SimpleNamespace

from src.main import SuperMenu


class FakeMainWindow:
    def __init__(self, visible):
        self.visible = visible
        self.hide_calls = 0

    def isVisible(self):
        return self.visible

    def hide(self):
        self.visible = False
        self.hide_calls += 1


class FakeContextMenuManager:
    def __init__(self):
        self.show_calls = 0

    def show_menu(self):
        self.show_calls += 1


def _application_stub(main_window):
    return SimpleNamespace(
        main_window=main_window,
        context_menu_manager=FakeContextMenuManager(),
        hotkey_manager=SimpleNamespace(hotkey="Cmd+Shift+Space"),
    )


def test_global_menu_hides_visible_configuration_window_first():
    application = _application_stub(FakeMainWindow(visible=True))

    SuperMenu.show_context_menu(application)

    assert application.main_window.hide_calls == 1
    assert application.context_menu_manager.show_calls == 1


def test_global_menu_does_not_touch_already_hidden_configuration_window():
    application = _application_stub(FakeMainWindow(visible=False))

    SuperMenu.show_context_menu(application)

    assert application.main_window.hide_calls == 0
    assert application.context_menu_manager.show_calls == 1

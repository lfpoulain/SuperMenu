from PySide6.QtWidgets import QApplication

from src.ui import response_window as response_window_module
from src.ui.response_window import ResponseWindow


def test_response_write_uses_async_target_insertion(monkeypatch):
    QApplication.instance() or QApplication([])
    calls = []

    class FakeInserter:
        def insert_text_async(self, text, target, callback):
            calls.append((text, target))
            callback(True, "")

    monkeypatch.setattr(
        response_window_module,
        "TextInserter",
        FakeInserter,
    )
    window = ResponseWindow()
    target = object()
    window.set_paste_target(target)
    window._pending_paste_text = "réponse"

    window._paste_text()

    assert calls == [("réponse", target)]
    assert window._active_text_inserter is None
    assert window.write_button.isEnabled() is True
    window.close()

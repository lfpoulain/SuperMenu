import sys

import pytest
from PySide6.QtWidgets import QApplication


@pytest.mark.skipif(sys.platform != "darwin", reason="Native AppKit status item")
def test_native_status_item_dispatch_is_queued_and_cleanup_is_idempotent():
    from AppKit import NSApplication
    from src.ui.status_item import NativeStatusItem

    NSApplication.sharedApplication()
    app = QApplication.instance() or QApplication([])
    calls = []
    tray = NativeStatusItem(
        "/missing-icon.png", [("Ouvrir", lambda: calls.append("open")), None]
    )
    tray._target.invoke_(tray._menu.itemAtIndex_(0))
    assert not calls
    app.processEvents()
    assert calls == ["open"]
    tray._target.invoke_(tray._menu.itemAtIndex_(0))
    tray.hide()
    tray.hide()
    app.processEvents()
    assert calls == ["open"]

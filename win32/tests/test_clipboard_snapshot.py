"""Clipboard snapshots: the user's content comes back intact and
SuperMenu's own writes stay out of the clipboard history."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QMimeData
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from src.utils import clipboard_manager as clipboard_module
from src.utils.clipboard_manager import ClipboardManager, ClipboardSnapshot


HISTORY = 'application/x-qt-windows-mime;value="CanIncludeInClipboardHistory"'
CLOUD = 'application/x-qt-windows-mime;value="CanUploadToCloudClipboard"'
MONITORS = 'application/x-qt-windows-mime;value="ExcludeClipboardContentFromMonitorProcessing"'


def _app():
    return QApplication.instance() or QApplication([])


def _release_clipboard(app):
    # Same teardown as test_safety_regressions: release the offscreen clipboard.
    app.clipboard().clear()
    app.processEvents()


def test_snapshot_restores_a_copied_image_instead_of_an_empty_one():
    app = _app()
    image = QImage(4, 3, QImage.Format_ARGB32)
    image.fill(QColor(10, 20, 30))
    mime = QMimeData()
    mime.setImageData(image)
    mime.setText("légende")
    app.clipboard().setMimeData(mime)
    try:
        snapshot = ClipboardManager.capture_snapshot()
        # QMimeData.data() returns 0 bytes for the image: it must not be kept.
        assert "application/x-qt-image" not in snapshot.formats
        assert snapshot.image is not None

        app.clipboard().setText("__SUPERMENU_EMPTY_SELECTION__")
        assert snapshot.restore() is True

        restored = app.clipboard().mimeData()
        assert restored.text() == "légende"
        restored_image = app.clipboard().image()
        assert not restored_image.isNull()
        assert restored_image.size() == image.size()
        assert restored_image.pixelColor(0, 0).getRgb() == (10, 20, 30, 255)
    finally:
        _release_clipboard(app)


def test_restore_puts_user_content_back_as_it_was_without_history_markers():
    # Restored content must return to the top of Win+V and of the cloud
    # clipboard, as before: only SuperMenu's transient writes are excluded.
    app = _app()
    mime = QMimeData()
    mime.setText("original")
    app.clipboard().setMimeData(mime)
    try:
        snapshot = ClipboardManager.capture_snapshot()
        app.clipboard().setText("temporaire")
        snapshot.restore()

        restored = app.clipboard().mimeData()
        assert restored.text() == "original"
        for marker in (HISTORY, CLOUD, MONITORS):
            assert marker not in restored.formats()
    finally:
        _release_clipboard(app)


def test_restore_preserves_exclusion_set_by_a_password_manager():
    app = _app()
    mime = QMimeData()
    mime.setText("secret")
    mime.setData(MONITORS, QByteArray(b"\x01\x00\x00\x00"))
    mime.setData(HISTORY, QByteArray(b"\x00\x00\x00\x00"))
    app.clipboard().setMimeData(mime)
    try:
        snapshot = ClipboardManager.capture_snapshot()
        app.clipboard().setText("temporaire")
        snapshot.restore()

        restored = app.clipboard().mimeData()
        assert restored.text() == "secret"
        assert bytes(restored.data(MONITORS)) == b"\x01\x00\x00\x00"
        assert bytes(restored.data(HISTORY)) == b"\x00\x00\x00\x00"
    finally:
        _release_clipboard(app)


def test_restoring_an_empty_clipboard_adds_no_marker():
    app = _app()
    app.clipboard().setText("temporaire")
    try:
        assert ClipboardSnapshot({}).restore() is True
        assert app.clipboard().mimeData().formats() == []
    finally:
        _release_clipboard(app)


class FakeWin32Clipboard:
    def __init__(self, fail_markers=False):
        self.calls = []
        self.fail_markers = fail_markers

    def OpenClipboard(self):
        self.calls.append("open")

    def CloseClipboard(self):
        self.calls.append("close")

    def EmptyClipboard(self):
        self.calls.append("empty")

    def SetClipboardText(self, text, _format):
        self.calls.append(("text", text))

    def RegisterClipboardFormat(self, name):
        return name

    def SetClipboardData(self, clipboard_format, value):
        if self.fail_markers:
            raise RuntimeError("format refused")
        self.calls.append(("data", clipboard_format, value))


def test_transient_writes_are_excluded_from_history_cloud_and_monitors(monkeypatch):
    fake = FakeWin32Clipboard()
    monkeypatch.setattr(clipboard_module, "win32clipboard", fake)

    assert ClipboardManager.set_clipboard_text_safe("marqueur", transient=True) is True

    markers = {call[1]: call[2] for call in fake.calls if call[0] == "data"}
    assert markers == {
        "ExcludeClipboardContentFromMonitorProcessing": b"\x00\x00\x00\x00",
        "CanIncludeInClipboardHistory": b"\x00\x00\x00\x00",
        "CanUploadToCloudClipboard": b"\x00\x00\x00\x00",
    }
    assert fake.calls.index(("text", "marqueur")) < fake.calls.index(
        ("data", "CanIncludeInClipboardHistory", b"\x00\x00\x00\x00")
    )
    assert fake.calls[-1] == "close"


def test_default_writes_are_unchanged_and_marker_failures_are_harmless(monkeypatch):
    fake = FakeWin32Clipboard()
    monkeypatch.setattr(clipboard_module, "win32clipboard", fake)
    assert ClipboardManager.set_clipboard_text_safe("copie") is True
    assert not [call for call in fake.calls if call[0] == "data"]

    failing = FakeWin32Clipboard(fail_markers=True)
    monkeypatch.setattr(clipboard_module, "win32clipboard", failing)
    assert ClipboardManager.set_clipboard_text_safe("réponse", transient=True) is True
    assert ("text", "réponse") in failing.calls

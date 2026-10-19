"""Screen capture: physical coordinates, several screens and response
windows hidden during the capture."""

import os
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtCore import SIGNAL, QPoint, QRect
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from src.ui import screen_capture


@pytest.fixture
def app(monkeypatch):
    application = QApplication.instance() or QApplication([])
    # Déclenche la capture sans faire tourner la boucle Qt : des minuteries
    # laissées par d'autres tests ne doivent pas s'exécuter ici.
    started = []

    class Timer:
        def __init__(self):
            self._slots = []
            self.timeout = SimpleNamespace(connect=self._slots.append)

        def setSingleShot(self, _single_shot):
            pass

        def start(self, _delay_ms):
            started.append(self)

    class Loop:
        def exec(self):
            while started:
                for slot in started.pop(0)._slots:
                    slot()

        def quit(self):
            pass

    monkeypatch.setattr(screen_capture, "QTimer", Timer)
    monkeypatch.setattr(screen_capture, "QEventLoop", Loop)
    monkeypatch.setattr(
        screen_capture,
        "QApplication",
        SimpleNamespace(topLevelWidgets=QApplication.topLevelWidgets, processEvents=lambda: None),
    )
    return application


class _FakeScreen:
    """Écran secondaire à 150 % : géométrie logique, capture en pixels physiques."""

    def __init__(self, geometry, ratio=1.5):
        self._geometry = QRect(geometry)
        self._ratio = ratio
        self.calls = []

    def geometry(self):
        return QRect(self._geometry)

    def grabWindow(self, window, x, y, width, height):
        self.calls.append((window, x, y, width, height))
        pixmap = QPixmap(round(width * self._ratio), round(height * self._ratio))
        pixmap.fill(QColor("red"))
        return pixmap


def test_region_is_grabbed_in_screen_coordinates_on_a_scaled_secondary_screen(app):
    screen = _FakeScreen(QRect(-1280, 263, 853, 533))

    pixmap = screen_capture._grab_region(screen, QRect(-1200, 300, 100, 50))

    # Coordonnées logiques relatives à l'écran : Qt applique lui-même le
    # facteur d'échelle, l'image garde donc la résolution physique.
    assert screen.calls == [(0, 80, 37, 100, 50)]
    assert (pixmap.width(), pixmap.height()) == (150, 75)


def test_region_is_clipped_to_the_screen_and_empty_selection_is_rejected(app):
    screen = _FakeScreen(QRect(0, 0, 800, 600), ratio=1)

    screen_capture._grab_region(screen, QRect(700, 500, 300, 300))
    assert screen.calls == [(0, 700, 500, 100, 100)]
    assert screen_capture._grab_region(screen, QRect(900, 700, 50, 50)) is None


def test_region_capture_hides_response_windows_and_keeps_closed_dialogs_closed(
    app, monkeypatch
):
    class FakeResponseWindow(QWidget):
        pass

    monkeypatch.setattr(screen_capture, "BaseResponseWindow", FakeResponseWindow)
    screen = _FakeScreen(QRect(0, 0, 800, 600))
    dialog, closed_dialog, rejected_dialog = QDialog(), QDialog(), QDialog()
    response = FakeResponseWindow()
    widgets = (dialog, closed_dialog, rejected_dialog, response)
    for widget in widgets:
        widget.show()
    seen_during_capture = {}

    class FakeSelector:
        def exec(self):
            seen_during_capture.update(
                dialog=dialog.isVisible(),
                closed_dialog=closed_dialog.isVisible(),
                rejected_dialog=rejected_dialog.isVisible(),
                response=response.isVisible(),
            )
            # Une minuterie ferme l'indicateur pendant la sélection.
            closed_dialog.close()
            # QDialog absorbe le QCloseEvent de reject()/accept()/done().
            rejected_dialog.reject()
            return QDialog.Accepted

        def get_rect(self):
            return QRect(10, 20, 40, 30)

        def target_screen(self):
            return screen

    monkeypatch.setattr(screen_capture, "_RegionSelector", FakeSelector)
    path = screen_capture.capture_screen("region")
    try:
        assert seen_during_capture == {
            "dialog": False,
            "closed_dialog": False,
            "rejected_dialog": False,
            "response": False,
        }
        assert screen.calls == [(0, 10, 20, 40, 30)]
        with Image.open(path) as image:
            assert image.size == (60, 45)
        assert dialog.isVisible() and response.isVisible()
        assert not closed_dialog.isVisible()
        assert not rejected_dialog.isVisible()
        # La surveillance s'arrête avec la capture.
        assert dialog.receivers(SIGNAL("finished(int)")) == 0
    finally:
        if path and os.path.exists(path):
            os.remove(path)
        for widget in widgets:
            widget.hide()
            widget.deleteLater()


def test_region_capture_keeps_a_moved_response_window_in_place(app, monkeypatch):
    # La vraie fenêtre de réponse se replace dans showEvent à chaque affichage.
    response = screen_capture.BaseResponseWindow()
    response.show()
    response.move(20, 30)
    assert response.pos() == QPoint(20, 30)
    screen = _FakeScreen(QRect(0, 0, 800, 600), ratio=1)

    class FakeSelector:
        def exec(self):
            assert not response.isVisible()
            return QDialog.Accepted

        def get_rect(self):
            return QRect(10, 20, 40, 30)

        def target_screen(self):
            return screen

    monkeypatch.setattr(screen_capture, "_RegionSelector", FakeSelector)
    path = screen_capture.capture_screen("region")
    try:
        assert response.isVisible()
        assert response.pos() == QPoint(20, 30)
    finally:
        if path and os.path.exists(path):
            os.remove(path)
        response.hide()
        response.deleteLater()


def test_fullscreen_capture_still_uses_the_physical_primary_screen(app, monkeypatch):
    calls = []

    class FakeImageGrab:
        @staticmethod
        def grab(**kwargs):
            calls.append(kwargs)
            return Image.new("RGB", (32, 16))

    monkeypatch.setattr(screen_capture, "ImageGrab", FakeImageGrab)
    path = screen_capture.capture_screen("fullscreen")
    try:
        assert calls == [{}]
        with Image.open(path) as image:
            assert image.size == (32, 16)
    finally:
        if path and os.path.exists(path):
            os.remove(path)


def test_selector_covers_the_screen_under_the_cursor(app, monkeypatch):
    primary = QApplication.primaryScreen()
    monkeypatch.setattr(screen_capture, "_screen_under_cursor", lambda: primary)
    selector = screen_capture._RegionSelector()
    try:
        assert selector.target_screen() is primary
        assert selector.geometry().topLeft() == primary.geometry().topLeft()
        selector._start_pos = QPoint(0, 0)
        selector._end_pos = QPoint(39, 29)
        rect = selector.get_rect()
        assert rect.topLeft() == primary.geometry().topLeft()
        assert (rect.width(), rect.height()) == (40, 30)
    finally:
        selector.close()
        selector.deleteLater()

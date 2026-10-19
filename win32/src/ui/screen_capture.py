#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QRubberBand
from PySide6.QtCore import Qt, QTimer, QEventLoop, QRect, QObject, QEvent
from PySide6.QtGui import QGuiApplication, QPainter, QColor, QCursor
import os
import tempfile
import logging
from PIL import ImageGrab
from supermenu_core.ui.response_window import BaseResponseWindow
from src.utils.logger import log


def _screen_under_cursor():
    """Écran sur lequel l'utilisateur travaille (écran principal par défaut)."""
    try:
        screen = QGuiApplication.screenAt(QCursor.pos())
    except Exception:
        screen = None
    return screen or QGuiApplication.primaryScreen()


def _grab_region(screen, rect):
    """Capture ``rect`` (coordonnées logiques Qt globales) sur ``screen``.

    QScreen.grabWindow attend des coordonnées logiques relatives à l'écran et
    applique lui-même le facteur d'échelle (125 %, 150 %…) : l'image obtenue
    est en pixels physiques et correspond exactement à la zone sélectionnée,
    y compris sur un écran secondaire d'origine négative.
    """
    screen_geometry = screen.geometry()
    rect = QRect(rect).intersected(screen_geometry)
    if rect.isEmpty():
        return None
    pixmap = screen.grabWindow(
        0,
        rect.x() - screen_geometry.x(),
        rect.y() - screen_geometry.y(),
        rect.width(),
        rect.height(),
    )
    if pixmap is None or pixmap.isNull():
        return None
    return pixmap


def _should_hide_during_capture(widget):
    """Fenêtres SuperMenu qui ne doivent pas apparaître dans la capture."""
    return isinstance(widget, (QDialog, BaseResponseWindow)) and widget.isVisible()


class _CloseWatcher(QObject):
    """Retient les fenêtres fermées pendant la capture pour ne pas les rouvrir."""

    def __init__(self):
        super().__init__()
        self.closed = set()
        self._finished_slots = {}

    def watch(self, widget):
        widget.installEventFilter(self)
        if isinstance(widget, QDialog):
            # accept(), reject() et done() ferment un QDialog sans que son
            # QCloseEvent n'atteigne ce filtre (Qt >= 6.3 l'absorbe) : seul
            # le signal finished signale ces fermetures.
            def _on_finished(_result, key=id(widget)):
                self.closed.add(key)

            widget.finished.connect(_on_finished)
            self._finished_slots[id(widget)] = _on_finished

    def unwatch(self, widget):
        try:
            widget.removeEventFilter(self)
        except Exception:
            pass
        slot = self._finished_slots.pop(id(widget), None)
        if slot is not None:
            try:
                widget.finished.disconnect(slot)
            except Exception:
                pass

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Close:
            self.closed.add(id(watched))
        return False


class _RegionSelector(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_pos = None
        self._end_pos = None
        self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setWindowModality(Qt.ApplicationModal)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CrossCursor))
        self.setFocusPolicy(Qt.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self._label = QLabel("Sélectionnez une zone (Échap pour annuler)")
        self._label.setObjectName("captureHint")
        layout.addWidget(self._label, alignment=Qt.AlignLeft | Qt.AlignTop)
        layout.addStretch()

        # Une fenêtre plein écran ne couvre qu'un écran : on choisit celui du
        # curseur, et la sélection est capturée sur ce même écran.
        self._target_screen = _screen_under_cursor()
        if self._target_screen is not None:
            try:
                self.setScreen(self._target_screen)
            except Exception:
                pass
            self.setGeometry(self._target_screen.geometry())

        try:
            self.showFullScreen()
        except Exception:
            pass

        try:
            self.raise_()
            self.activateWindow()
            self.setFocus()
        except Exception:
            pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))
        painter.end()

    def target_screen(self):
        """Écran réellement couvert par la sélection."""
        try:
            screen = self.screen()
        except Exception:
            screen = None
        return screen or self._target_screen or QGuiApplication.primaryScreen()

    def get_rect(self):
        if self._start_pos is None or self._end_pos is None:
            return None
        r = QRect(self._start_pos, self._end_pos).normalized()
        if r.width() < 5 or r.height() < 5:
            return None
        r.translate(self.geometry().topLeft())
        return r

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start_pos = event.position().toPoint()
            self._end_pos = self._start_pos
            self._rubber_band.setGeometry(QRect(self._start_pos, self._end_pos))
            self._rubber_band.show()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._start_pos is not None:
            self._end_pos = event.position().toPoint()
            self._rubber_band.setGeometry(QRect(self._start_pos, self._end_pos).normalized())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._start_pos is not None:
            self._end_pos = event.position().toPoint()
            self._rubber_band.hide()
            if self.get_rect() is None:
                self.reject()
            else:
                self.accept()
        super().mouseReleaseEvent(event)


def capture_screen(mode: str = "fullscreen"):
    """Fonction pour capturer une zone de l'écran et retourner le chemin de l'image"""
    log("Démarrage de la capture d'écran simplifiée...", logging.DEBUG)
    
    # Masquer les dialogues et la fenêtre de réponse (toujours au premier
    # plan) pour qu'ils n'apparaissent pas dans l'image envoyée à l'IA.
    hidden_dialogs = []
    positions = {}
    close_watcher = _CloseWatcher()
    for widget in QApplication.topLevelWidgets():
        if _should_hide_during_capture(widget):
            hidden_dialogs.append(widget)
            if isinstance(widget, BaseResponseWindow):
                # Son showEvent la replace à chaque affichage : garder la
                # position choisie par l'utilisateur.
                positions[id(widget)] = widget.pos()
            close_watcher.watch(widget)
            widget.hide()
    
    # Attendre un court instant pour que les fenêtres disparaissent
    QApplication.processEvents()
    
    # Créer un timer pour retarder la capture
    timer = QTimer()
    timer.setSingleShot(True)
    
    # Variables pour stocker le résultat
    screenshot_path = None
    loop = QEventLoop()
    
    def do_capture():
        nonlocal screenshot_path
        try:
            if mode == "region":
                selector = _RegionSelector()
                if selector.exec() != QDialog.Accepted:
                    screenshot_path = None
                    return
                rect = selector.get_rect()
                if rect is None:
                    screenshot_path = None
                    return
                screenshot = _grab_region(selector.target_screen(), rect)
                if screenshot is None:
                    log("Zone de capture vide ou hors écran", logging.WARNING)
                    screenshot_path = None
                    return
            else:
                screenshot = ImageGrab.grab()
            
            # Créer un fichier temporaire pour stocker l'image
            temp_dir = tempfile.gettempdir()
            path = os.path.join(temp_dir, f"supermenu_screenshot_{id(timer)}.png")
            
            # Enregistrer l'image (QPixmap.save renvoie False en cas d'échec)
            if screenshot.save(path, "PNG") is False:
                raise OSError(f"impossible d'enregistrer {path}")
            screenshot_path = path
            log(f"Image capturée et enregistrée: {screenshot_path}", logging.DEBUG)
        except Exception as e:
            log(f"Erreur lors de la capture d'écran: {e}", logging.ERROR)
            screenshot_path = None
        finally:
            pass
    
    # Connecter le timer à la fonction de capture
    def _on_timeout():
        do_capture()
        loop.quit()
    timer.timeout.connect(_on_timeout)
    
    # Démarrer le timer (500 ms de délai)
    timer.start(500)
    loop.exec()

    for widget in hidden_dialogs:
        try:
            close_watcher.unwatch(widget)
            # Une fenêtre fermée pendant la capture (minuterie, fin de
            # requête…) doit rester fermée ; une fenêtre réaffichée entre-temps
            # par l'application garde la position que celle-ci lui a donnée.
            if id(widget) in close_watcher.closed or widget.isVisible():
                continue
            widget.show()
            position = positions.get(id(widget))
            if position is not None:
                widget.move(position)
        except Exception:
            pass

    return screenshot_path

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QRubberBand, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt, QTimer, QEventLoop, QRect
from PySide6.QtGui import QGuiApplication, QPainter, QColor, QCursor
import os
import tempfile
import logging
from PIL import ImageGrab
from src.utils.logger import log

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
        self._label.setStyleSheet("background: rgba(0,0,0,0.6); padding: 6px; border-radius: 6px;")
        layout.addWidget(self._label, alignment=Qt.AlignLeft | Qt.AlignTop)
        layout.addStretch()

        geom = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geom)

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


class _CaptureModeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = None
        self.setWindowTitle("Capture d'écran")
        self.setWindowFlags(Qt.Popup | Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        label = QLabel("Choisir le type de capture")
        layout.addWidget(label)

        buttons = QHBoxLayout()
        fullscreen_btn = QPushButton("Plein écran")
        region_btn = QPushButton("Sélection de zone")
        cancel_btn = QPushButton("Annuler")

        fullscreen_btn.clicked.connect(lambda: self._select("fullscreen"))
        region_btn.clicked.connect(lambda: self._select("region"))
        cancel_btn.clicked.connect(self.reject)

        buttons.addWidget(fullscreen_btn)
        buttons.addWidget(region_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def _select(self, mode: str):
        self._mode = mode
        self.accept()

    def get_mode(self):
        return self._mode


def choose_capture_mode(parent=None):
    dlg = _CaptureModeDialog(parent)
    cursor_pos = QCursor.pos()
    screen = QGuiApplication.screenAt(cursor_pos)
    if screen is not None:
        available = screen.availableGeometry()
        dlg.adjustSize()
        size = dlg.size()

        x = cursor_pos.x() + 12
        y = cursor_pos.y() + 12
        if x + size.width() > available.right():
            x = available.right() - size.width()
        if y + size.height() > available.bottom():
            y = available.bottom() - size.height()
        if x < available.left():
            x = available.left()
        if y < available.top():
            y = available.top()
        dlg.move(x, y)

    if dlg.exec() != QDialog.Accepted:
        return None
    return dlg.get_mode()


def capture_screen(mode: str = "fullscreen"):
    """Fonction pour capturer une zone de l'écran et retourner le chemin de l'image"""
    log("Démarrage de la capture d'écran simplifiée...", logging.DEBUG)
    
    hidden_dialogs = []
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QDialog) and widget.isVisible():
            hidden_dialogs.append(widget)
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
                bbox = (rect.left(), rect.top(), rect.right(), rect.bottom())
                screenshot = ImageGrab.grab(bbox=bbox)
            else:
                screenshot = ImageGrab.grab()
            
            # Créer un fichier temporaire pour stocker l'image
            temp_dir = tempfile.gettempdir()
            screenshot_path = os.path.join(temp_dir, f"supermenu_screenshot_{id(timer)}.png")
            
            # Enregistrer l'image
            screenshot.save(screenshot_path, "PNG")
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
            widget.show()
        except Exception:
            pass

    return screenshot_path

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu, QListWidget

from supermenu_core.ui.controls import (
    ChoiceBox, Menu, menu_contains_global_point, populate_prompt_menu,
)
from supermenu_core.ui.theme_manager import ThemeManager


@pytest.fixture
def app():
    instance = QApplication.instance() or QApplication([])
    font, palette, stylesheet = instance.font(), instance.palette(), instance.styleSheet()
    yield instance
    instance.setFont(font)
    instance.setStyleSheet(stylesheet)
    instance.setPalette(palette)


def test_dropdown_ignores_page_scrolling_but_keeps_keyboard_navigation(app):
    combo = ChoiceBox()
    combo.addItems(["Premier", "Indisponible", "Dernier"])
    combo.model().item(1).setEnabled(False)
    wheel = QWheelEvent(
        QPointF(5, 5), QPointF(5, 5), QPoint(), QPoint(0, -120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate, False,
    )
    QApplication.sendEvent(combo, wheel)
    assert combo.currentIndex() == 0
    assert not wheel.isAccepted()
    QTest.keyClick(combo, Qt.Key.Key_Down)
    assert combo.currentIndex() == 2


def test_prompt_menu_preserves_order_payloads_and_disabled_state(app):
    menu = Menu()
    prompts = {"later": {"name": "Plus tard", "position": 4}, "first": {"name": "D’abord", "position": 0}}
    populate_prompt_menu(menu, prompts, lambda key: ("prompt", key, "texte"), enabled=False)
    assert [action.text() for action in menu.actions()] == ["D’abord", "Plus tard"]
    assert [action.data() for action in menu.actions()] == [
        ("prompt", "first", "texte"), ("prompt", "later", "texte"),
    ]
    assert not any(action.isEnabled() for action in menu.actions())


def test_outside_click_detection_includes_visible_nested_menus(app):
    menu = Menu()
    submenu = menu.addMenu("Reformuler")
    nested = submenu.addMenu("Langue")
    nested.addAction("Français")
    # The existing-menu overload still returns a QAction, just like Qt.
    existing = QMenu("Existant")
    assert menu.addMenu(existing).menu() is existing
    try:
        menu.popup(QPoint(20, 20))
        submenu.popup(QPoint(240, 20))
        nested.popup(QPoint(460, 20))
        app.processEvents()
        point = nested.mapToGlobal(nested.rect().center())
        assert not menu.geometry().contains(point)
        assert menu_contains_global_point(menu, point)
        nested.hide()
        assert not menu_contains_global_point(menu, point)
        assert not menu_contains_global_point(menu, QPoint(-100, -100))
    finally:
        nested.hide()
        submenu.hide()
        menu.hide()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_selection_looks_the_same_in_menu_dropdown_and_inactive_list(app, theme):
    """Catch native/base-theme rules overriding just one kind of popup."""
    ThemeManager.apply_theme(app, theme)
    menu = Menu()
    action = menu.addAction("Action")
    combo = ChoiceBox()
    combo.addItems(["Choix", "Autre choix"])
    combo.resize(300, 44)
    listing = QListWidget()
    listing.addItems(["Action", "Autre action"])
    listing.setCurrentRow(0)
    listing.resize(300, 160)
    try:
        listing.show()
        combo.show()
        menu.popup(QPoint(20, 20))
        menu.setActiveAction(action)
        app.processEvents()
        rect = menu.actionGeometry(action)
        menu_colour = menu.grab().toImage().pixelColor(rect.right() - 16, rect.center().y())
        menu.hide()
        combo.showPopup()
        app.processEvents()
        index = combo.model().index(0, 0)
        rect = combo.view().visualRect(index)
        popup_colour = combo.view().viewport().grab().toImage().pixelColor(rect.right() - 16, rect.center().y())
        rect = listing.visualItemRect(listing.item(0))
        list_colour = listing.viewport().grab().toImage().pixelColor(rect.right() - 16, rect.center().y())
        assert menu_colour == popup_colour == list_colour
    finally:
        combo.hidePopup()
        combo.hide()
        menu.hide()
        listing.hide()

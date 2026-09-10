"""Desktop controls with shared popup, selection and keyboard behaviour."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QListView, QMenu, QWidget


class ChoiceBox(QComboBox):
    """Use the same item view for editable and non-editable dropdowns."""

    def __init__(self, parent=None):
        super().__init__(parent)
        popup = QListView(self)
        popup.setObjectName("choicePopup")
        popup.setUniformItemSizes(True)
        popup.setMouseTracking(True)
        popup.setSpacing(2)
        popup.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setView(popup)
        container = popup.window()
        container.setObjectName("choicePopupContainer")
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMaxVisibleItems(10)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        # Scrolling a settings page must never silently change a preference.
        # The open popup handles its own scrolling through its item view.
        event.ignore()


class Menu(QMenu):
    """One menu configuration, inherited by every nested submenu."""

    def __init__(self, *args):
        super().__init__(*args)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setToolTipsVisible(True)
        self.setSeparatorsCollapsible(True)

    def addMenu(self, *args):
        # Preserve QMenu's overloads: a title (optionally with an icon) returns
        # a menu, whereas adding an existing QMenu returns its QAction.
        if len(args) in (1, 2) and isinstance(args[-1], str):
            submenu = Menu(args[-1], self)
            if len(args) == 2:
                submenu.setIcon(args[0])
            super().addMenu(submenu)
            return submenu
        return super().addMenu(*args)


def menu_contains_global_point(menu, point):
    """Include visible descendants when deciding whether a click is outside."""
    if menu.isVisible() and menu.rect().contains(menu.mapFromGlobal(point)):
        return True
    return any(
        menu_contains_global_point(action.menu(), point)
        for action in menu.actions()
        if action.menu() is not None and action.menu().isVisible()
    )


def populate_prompt_menu(menu, prompts, data_for, *, enabled=True):
    """Preserve user ordering, labels and action data on both platforms."""
    for prompt_id, prompt in sorted(
        prompts.items(), key=lambda item: item[1].get("position", 999)
    ):
        action = menu.addAction(prompt["name"])
        action.setEnabled(enabled)
        action.setData(data_for(prompt_id))


def set_ui_property(widget, name, value, *, descendants=False):
    """Apply a semantic style property immediately, including state changes."""
    widget.setProperty(name, value)
    widgets = [widget]
    if descendants:
        widgets.extend(widget.findChildren(QWidget))
    for child in widgets:
        child.style().unpolish(child)
        child.style().polish(child)
        child.update()

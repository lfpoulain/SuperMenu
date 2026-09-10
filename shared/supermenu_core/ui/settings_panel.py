"""Small settings pages and explicit disclosure of optional controls."""

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QScrollArea,
    QFrame,
    QToolButton,
    QLayout,
    QFormLayout,
)


def form_layout(parent, *, stacked=False):
    """Use the same field growth and vertical rhythm on each platform."""
    form = QFormLayout(parent)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setVerticalSpacing(10)
    if stacked:
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
    return form


def scrollable_form(form):
    """Keep every field reachable when a window is small or text is enlarged."""
    form.layout().setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(form)
    return scroll


class Disclosure(QWidget):
    def __init__(self, title="Options avancées", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.toggle = QToolButton()
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.setAccessibleName(title)
        layout.addWidget(self.toggle)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 8, 0, 4)
        self.content_layout.setSpacing(8)
        layout.addWidget(self.content)
        self.content.hide()
        self.toggle.toggled.connect(self.set_expanded)

    def set_expanded(self, expanded):
        self.toggle.setChecked(expanded)
        self.toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.content.setVisible(expanded)


class SettingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(18)
        self.navigation = QListWidget()
        self.navigation.setObjectName("settingsNavigation")
        self.navigation.setAccessibleName("Rubriques des réglages")
        self.navigation.setFixedWidth(165)
        self.navigation.setFrameShape(QFrame.Shape.NoFrame)
        self.navigation.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.navigation.setSpacing(4)
        layout.addWidget(self.navigation)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.keys = []
        self.page_layouts = {}
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)

    def add_page(self, key, title, description):
        self.keys.append(key)
        item = QListWidgetItem(title)
        item.setSizeHint(QSize(145, 44))
        self.navigation.addItem(item)
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(10)
        self.page_layouts[key] = page_layout
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 2, 12, 12)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)
        subtitle = QLabel(description)
        subtitle.setObjectName("mutedText")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        scroll.setWidget(content)
        page_layout.addWidget(scroll, 1)
        self.pages.addWidget(page)
        if self.navigation.currentRow() < 0:
            self.navigation.setCurrentRow(0)
        return layout

    def select_page(self, key):
        self.navigation.setCurrentRow(self.keys.index(key))

    def set_footer(self, key, widget):
        self.page_layouts[key].addWidget(widget)

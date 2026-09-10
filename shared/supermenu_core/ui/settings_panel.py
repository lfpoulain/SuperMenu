"""Small settings pages and explicit disclosure of optional controls."""

from PySide6.QtCore import Qt
from .controls import SidebarList, SIDEBAR_WIDTH
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
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
    form.setVerticalSpacing(6)
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
        self.content_layout.setContentsMargins(8, 4, 0, 2)
        self.content_layout.setSpacing(6)
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
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        self.navigation = SidebarList()
        self.navigation.setObjectName("settingsNavigation")
        self.navigation.setAccessibleName("Rubriques des réglages")
        self.navigation.setFixedWidth(SIDEBAR_WIDTH)
        layout.addWidget(self.navigation)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.keys = []
        self.page_layouts = {}
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)

    def add_standard_pages(self):
        return {
            key: self.add_page(key, title, description)
            for key, title, description in (
                ("text", "Texte", "Choisissez l’IA pour corriger, reformuler et traduire vos textes."),
                ("voice", "Dictée", "Testez votre microphone, puis choisissez où transcrire votre voix."),
                ("shortcuts", "Raccourcis", "Accédez à SuperMenu depuis vos applications."),
                ("app", "Application", "Personnalisez l’apparence et gérez vos préférences."),
            )
        }

    def set_save_action(self, key, callback, label="Enregistrer"):
        from .page_actions import PageActions

        actions = PageActions()
        button = actions.add_action(label, callback, primary=True)
        self.set_footer(key, actions)
        return button

    def add_page(self, key, title, description):
        self.keys.append(key)
        item = QListWidgetItem(title)
        self.navigation.addItem(item)
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(6)
        self.page_layouts[key] = page_layout
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 2, 8, 8)
        layout.setSpacing(8)
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

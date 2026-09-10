"""Semantic colours and widget styles shared by the two desktop apps."""

ACCENT_COLORS = {
    "primary": "#3498db", "success": "#2ecc71", "warning": "#f39c12",
    "danger": "#e74c3c", "info": "#9b59b6",
}

PALETTES = {
    "dark": {
        "canvas": "#202124", "surface": "#292A2D", "field": "#242528",
        "hover": "#303A45", "border": "#45474B", "text": "#E4E7EB",
        "muted": "#ADB5C2", "accent": ACCENT_COLORS['primary'], "accent_hover": "#2980b9",
        "accent_text": "#FFFFFF", "selection": "#293E50", "selected_text": "#EFF1F1",
        "disabled": "#858B94",
    },
    "light": {
        "canvas": "#F8F9FA", "surface": "#FFFFFF", "field": "#F8F9FA",
        "hover": "#EDF3F8", "border": "#DADCE0", "text": "#4D5157",
        "muted": "#606872", "accent": ACCENT_COLORS['primary'], "accent_hover": "#2980b9",
        "accent_text": "#FFFFFF", "selection": "#DEEDF8", "selected_text": "#233F55",
        "disabled": "#80868B",
    },
}

# These accessible status colours were already used by the model verification
# panels. Keep them here so dialogs and panels use the same feedback palette.
STATUS_PALETTES = {
    "dark": {
        "idle": ("#adb5c2", "#292d34"), "busy": ("#89baff", "#20334c"),
        "info": ("#89baff", "#20334c"), "success": ("#7cddb0", "#1d382e"),
        "warning": ("#ffd080", "#403321"), "error": ("#ffa39d", "#422a2c"),
    },
    "light": {
        "idle": ("#556174", "#f0f3f7"), "busy": ("#195bab", "#edf5ff"),
        "info": ("#195bab", "#edf5ff"), "success": ("#17643f", "#edf8f1"),
        "warning": ("#845009", "#fff6e7"), "error": ("#ae302d", "#fff0ef"),
    },
}


def selection_styles(c):
    """A single state treatment for menus, dropdowns and navigation lists."""
    items = ("QMenu::item", "QListView::item", "QComboBox QAbstractItemView::item")
    rules = []
    for item in items:
        rules.append(f"""
        {item} {{ border: 1px solid transparent; border-radius: 6px; }}
        {item}:selected, {item}:selected:!active,
        {item}:selected:hover {{ background: {c['selection']}; color: {c['selected_text']}; }}
        {item}:disabled, {item}:disabled:selected {{
            background: transparent; color: {c['disabled']};
        }}
        """)
    return "\n".join(rules)


def widget_styles(theme="dark", font_size=10.5):
    c = {**PALETTES[theme], "error": STATUS_PALETTES[theme]["error"][0]}
    styles = f"""
    QWidget {{ color: {c['text']}; background: transparent; font-size: {font_size}pt; }}
    QMainWindow, QDialog, QWidget#desktopRoot, QWidget#responseWindow {{
        background-color: {c['canvas']};
    }}
    QLabel {{ background: transparent; }}
    QLabel#brandMark {{
        background: {c['accent']}; color: {c['accent_text']};
        border-radius: 13px; font-size: 25px; font-weight: 700;
    }}
    QLabel#brandTitle {{ font-size: 19px; font-weight: 700; }}
    QLabel#pageTitle {{ font-size: 24px; font-weight: 600; }}
    QLabel#mutedText {{ color: {c['muted']}; }}
    QLabel#fieldLabel {{ font-weight: 600; margin-top: 6px; }}
    QLabel#shortcutDisplay {{
        background: {c['field']}; border: 1px solid {c['border']};
        border-radius: 8px; padding: 12px; font-size: 16px; font-weight: 600;
    }}
    QLabel#aboutTitle {{ font-size: 28px; font-weight: 600; padding: 20px; }}
    QDialog#loadingIndicator {{
        background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px;
    }}
    QDialog#loadingIndicator QLabel {{ color: {c['text']}; padding: 12px 18px; }}
    QLabel#captureHint {{ background: rgba(0,0,0,0.6); color: white; padding: 6px; border-radius: 6px; }}
    QPushButton {{
        background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']};
        border-radius: 9px; padding: 8px 14px; font-weight: 500;
    }}
    QPushButton:hover {{ background: {c['hover']}; }}
    QPushButton:pressed {{ background: {c['selection']}; }}
    QPushButton:focus {{ border: 1px solid {c['accent']}; }}
    QPushButton:default, QPushButton[variant="primary"] {{
        background: {c['accent']}; color: {c['accent_text']};
        border: 1px solid {c['accent']}; font-weight: 600;
    }}
    QPushButton:default:hover, QPushButton[variant="primary"]:hover {{
        background: {c['accent_hover']}; border-color: {c['accent_hover']};
    }}
    QPushButton:default:pressed, QPushButton[variant="primary"]:pressed {{
        background: {c['accent_hover']}; border-color: {c['text']};
    }}
    QPushButton:default:focus, QPushButton[variant="primary"]:focus {{
        border: 1px solid {c['text']};
    }}
    QPushButton[variant="danger"] {{ color: {c['error']}; }}
    QPushButton:disabled, QPushButton:default:disabled, QPushButton:default:disabled:hover,
    QPushButton[variant="primary"]:disabled, QPushButton[variant="primary"]:disabled:hover,
    QPushButton[variant="danger"]:disabled {{
        background: {c['field']}; color: {c['disabled']}; border-color: {c['border']};
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background: {c['field']}; color: {c['text']};
        border: 1px solid {c['border']}; border-radius: 8px; padding: 8px 10px;
        selection-background-color: {c['selection']};
        selection-color: {c['selected_text']};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
    QComboBox:focus, QComboBox:open, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {c['accent']}; }}
    QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{ color: {c['disabled']}; }}
    QComboBox {{ padding-right: 28px; }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox QAbstractItemView {{
        background: {c['surface']}; color: {c['text']};
        border: none; border-radius: 10px; padding: 6px;
        selection-background-color: {c['selection']}; selection-color: {c['selected_text']};
    }}
    QFrame#choicePopupContainer {{
        background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px;
    }}
    QComboBox QAbstractItemView::item {{ padding: 8px 12px; min-height: 20px; }}
    QComboBox QAbstractItemView::item:hover:!selected {{ background: {c['hover']}; }}
    QGroupBox {{
        background: {c['surface']}; border: 1px solid {c['border']};
        border-radius: 12px; margin-top: 14px; padding: 18px 12px 12px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin; subcontrol-position: top left;
        left: 16px; padding: 0 6px; background: {c['canvas']}; color: {c['muted']};
    }}
    QTabWidget::pane {{ border: none; background: {c['canvas']}; top: 8px; }}
    QTabBar {{ background: transparent; }}
    QTabBar::tab {{
        background: transparent; color: {c['muted']}; border: none;
        border-radius: 9px; padding: 10px 18px; margin-right: 6px;
    }}
    QTabBar::tab:selected {{ background: {c['selection']}; color: {c['selected_text']}; }}
    QTabBar::tab:top, QTabBar::tab:top:selected, QTabBar::tab:top:hover {{
        border: 1px solid transparent; border-radius: 9px; margin-left: 0;
    }}
    QTabBar::tab:hover:!selected {{ background: {c['hover']}; }}
    QTabBar::tab:focus, QTabBar::tab:top:selected:focus {{ border: 1px solid {c['accent']}; }}
    QListView {{
        background: {c['surface']}; border: 1px solid {c['border']};
        border-radius: 12px; padding: 6px; outline: none;
    }}
    QListView::item {{
        border: 1px solid transparent; border-radius: 8px; padding: 10px 8px;
    }}
    QListView::item:hover:!selected {{ background: {c['hover']}; }}
    QListView::item:focus {{ border: 1px solid {c['accent']}; }}
    QListWidget#settingsNavigation {{ background: transparent; border: none; padding: 0; }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 3px; min-height: 28px; }}
    QScrollBar::handle:vertical:hover {{ background: {c['muted']}; }}
    QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 3px; min-width: 28px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; border: none; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QCheckBox, QCheckBox:hover {{ spacing: 8px; background: transparent; border: none; }}
    QCheckBox:disabled {{ color: {c['disabled']}; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; margin: 0; }}
    QCheckBox::indicator:unchecked {{ image: none; background: {c['field']}; border: 1px solid {c['border']}; }}
    QCheckBox::indicator:checked {{ background: {c['accent']}; border: 1px solid {c['accent']}; }}
    QCheckBox::indicator:focus {{ border: 1px solid {c['text']}; }}
    QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 6px; }}
    QToolButton:hover {{ background: {c['hover']}; }}
    QToolButton:focus {{ border-color: {c['accent']}; }}
    QToolButton:checked {{ background: {c['selection']}; color: {c['selected_text']}; }}
    QToolButton:disabled {{ color: {c['disabled']}; }}
    QMenu {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 6px; }}
    QMenu::item {{ padding: 8px 24px; margin: 2px; border-radius: 6px; }}
    QMenu::right-arrow {{ width: 12px; height: 12px; margin-right: 6px; }}
    QMenu::separator {{ background: {c['border']}; height: 1px; margin: 5px 10px; }}
    QToolTip {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 6px; }}
    QFrame#imageFrame {{ border: 1px solid {c['border']}; border-radius: 10px; }}
    QProgressBar {{
        background: {c['field']}; border: 1px solid {c['border']}; border-radius: 4px;
        text-align: center; color: {c['text']};
    }}
    QProgressBar::chunk {{ background: {c['accent']}; border-radius: 3px; }}
    QTextEdit#responseText {{ padding: 18px; font-size: 15px; background: {c['surface']}; }}
    """
    for state, (accent, _background) in STATUS_PALETTES[theme].items():
        styles += f'QLabel[status="{state}"] {{ color: {accent}; }}\n'
    return styles + selection_styles(c)

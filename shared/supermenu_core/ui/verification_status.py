"""Persistent, accessible feedback for local model availability checks."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
)


class VerificationStatus(QFrame):
    SYMBOLS = {
        "idle": "i",
        "busy": "…",
        "info": "i",
        "success": "✓",
        "warning": "!",
        "error": "!",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("verificationStatus")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        heading = QHBoxLayout()
        heading.setSpacing(10)
        self.icon = QLabel()
        self.icon.setObjectName("verificationIcon")
        self.icon.setFixedSize(26, 26)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.addWidget(self.icon)
        self.title = QLabel()
        self.title.setObjectName("verificationTitle")
        self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        heading.addWidget(self.title, 1)
        layout.addLayout(heading)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.detail)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setAccessibleName("Progression de la préparation du modèle")
        layout.addWidget(self.progress_bar)
        self.caption = QLabel()
        self.caption.setObjectName("verificationCaption")
        self.caption.setWordWrap(True)
        self.caption.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.caption)
        self.set_status("idle", "Disponibilité à vérifier", "")

    def set_status(self, state, title, detail, *, checked_at=""):
        self.setProperty("state", state)
        self.icon.setText(self.SYMBOLS[state])
        self.title.setText(title)
        self.detail.setText(detail)
        self.detail.setVisible(bool(detail))
        self.caption.setText(checked_at)
        self.caption.setVisible(bool(checked_at))
        self.progress_bar.setVisible(state == "busy")
        if state == "busy":
            self.progress_bar.setRange(0, 0)
        self.setAccessibleName(title)
        self.setAccessibleDescription(detail)
        # A dynamic property change does not automatically refresh Qt's QSS.
        for widget in (self, *self.findChildren(QLabel)):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def set_progress(self, percent):
        value = max(0, min(100, round(percent)))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(value)
        self.caption.setText(f"{value} % téléchargé")
        self.caption.show()

    @staticmethod
    def stylesheet(theme):
        # Text accents retain contrast on both backgrounds; colour always comes
        # with a symbol and a descriptive title.
        colours = (
            {
                "idle": ("#adb5c2", "#292d34"),
                "busy": ("#89baff", "#20334c"),
                "info": ("#89baff", "#20334c"),
                "success": ("#7cddb0", "#1d382e"),
                "warning": ("#ffd080", "#403321"),
                "error": ("#ffa39d", "#422a2c"),
            }
            if theme == "dark"
            else {
                "idle": ("#556174", "#f0f3f7"),
                "busy": ("#195bab", "#edf5ff"),
                "info": ("#195bab", "#edf5ff"),
                "success": ("#17643f", "#edf8f1"),
                "warning": ("#845009", "#fff6e7"),
                "error": ("#ae302d", "#fff0ef"),
            }
        )
        css = """
            QFrame#verificationStatus { border-radius: 9px; }
            QFrame#verificationStatus QLabel {
                background: transparent; border: none; padding: 0;
            }
            QLabel#verificationTitle { font-weight: 600; font-size: 15px; }
            QLabel#verificationIcon { font-size: 18px; font-weight: 600; }
            QLabel#verificationCaption { font-size: 11px; }
            QFrame#verificationStatus QProgressBar {
                border: none; border-radius: 3px; padding: 0;
            }
        """
        for state, (accent, background) in colours.items():
            selector = f'QFrame#verificationStatus[state="{state}"]'
            css += f"""
                {selector} {{
                    background-color: {background}; border: 1px solid {accent};
                }}
                {selector} QLabel#verificationTitle,
                {selector} QLabel#verificationIcon,
                {selector} QLabel#verificationCaption {{ color: {accent}; }}
            """
        return css

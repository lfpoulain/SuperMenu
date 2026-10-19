"""Shared product information and links; callbacks keep OS actions local."""

import html
import os
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

REPOSITORY_URL = "https://github.com/lfpoulain/SuperMenu"
LICENSE_NAME = "PolyForm Noncommercial 1.0.0"
LICENSE_URL = f"{REPOSITORY_URL}/blob/main/LICENSE"
THIRD_PARTY_NOTICES_FILE = "THIRD_PARTY_NOTICES.md"
THIRD_PARTY_NOTICES_URL = f"{REPOSITORY_URL}/blob/main/{THIRD_PARTY_NOTICES_FILE}"


def bundled_notices_path():
    """Return the third-party notices shipped inside a packaged build, if any.

    PyInstaller collects the file at the root of its bundle: the extraction
    folder on Windows, Contents/Frameworks (linked to Resources) on macOS.
    """
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if not getattr(sys, "frozen", False) or not bundle_dir:
        return None
    path = os.path.join(bundle_dir, THIRD_PARTY_NOTICES_FILE)
    return path if os.path.isfile(path) else None


def _link(url, text):
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(text)}</a>'


def license_links_html():
    links = " · ".join((
        _link(LICENSE_URL, "Lire la licence"),
        _link(THIRD_PARTY_NOTICES_URL, "Composants tiers"),
    ))
    local_notices = bundled_notices_path()
    if local_notices:
        local_url = QUrl.fromLocalFile(local_notices).toString()
        links += f" ({_link(local_url, 'copie locale')})"
    return links


class AboutPage(QWidget):
    def __init__(self, version, open_releases, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        for text, name in (
            ("SuperMenu", "aboutTitle"),
            (f"Version {version}", "mutedText"),
            ("Corrigez, reformulez, traduisez et dictez depuis vos applications.\n"
             "Retrouvez vos prompts et choisissez votre moteur IA dans les réglages.", "mutedText"),
            ("Développé par LFPoulain avec ❤️", "mutedText"),
            (f"Licence : {LICENSE_NAME}", "mutedText"),
        ):
            label = QLabel(text)
            label.setObjectName(name)
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
        links = QLabel(license_links_html())
        links.setObjectName("mutedText")
        links.setWordWrap(True)
        links.setAlignment(Qt.AlignmentFlag.AlignCenter)
        links.setTextFormat(Qt.TextFormat.RichText)
        links.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        links.setOpenExternalLinks(True)
        self.license_links = links
        layout.addWidget(links)
        button = QPushButton("Voir les versions publiées")
        button.clicked.connect(open_releases)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()

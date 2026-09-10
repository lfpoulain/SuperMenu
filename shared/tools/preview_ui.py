"""Exercise popups and feedback states without starting external services."""
import os
import sys
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'shared'))
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFontDatabase, QActionGroup
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
from supermenu_core.ui.controls import ChoiceBox, Menu
from supermenu_core.ui.theme_manager import ThemeManager
from supermenu_core.ui.loading_indicator import SimpleLoadingIndicator
from supermenu_core.ui.dictation_dialog import RecordingDialog
from supermenu_core.ui.verification_status import VerificationStatus

app = QApplication([])
font_directory = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
for name in ('segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf', 'seguiemj.ttf'):
    font = font_directory / name
    if font.exists():
        QFontDatabase.addApplicationFont(str(font))
output = root / 'build/ui-preview'
output.mkdir(exist_ok=True, parents=True)
def render(widget, name):
    app.processEvents()
    app.processEvents()
    assert widget.grab().save(str(output / name)), name

window = QWidget()
window.setObjectName('desktopRoot')
layout = QVBoxLayout(window)
layout.setContentsMargins(24, 24, 24, 24)
layout.setAlignment(Qt.AlignmentFlag.AlignTop)
title = QLabel('Composants partagés')
title.setObjectName('pageTitle')
layout.addWidget(title)
combo = ChoiceBox()
combo.addItems(['OpenAI', 'Ollama / LM Studio', 'IA locale Microsoft — Foundry Local', 'Moteur indisponible'])
combo.model().item(3).setEnabled(False)
layout.addWidget(combo)
editable = ChoiceBox()
editable.setEditable(True)
editable.addItems(['Modèle personnalisé', 'qwen3.5-4b'])
layout.addWidget(editable)
field = QLineEdit('Sélection de texte')
layout.addWidget(field)
buttons = QHBoxLayout()
for text, role, enabled in [('Enregistrer', 'primary', True), ('Annuler', 'secondary', True), ('Indisponible', 'primary', False)]:
    button = QPushButton(text)
    button.setProperty('variant', role)
    button.setEnabled(enabled)
    buttons.addWidget(button)
layout.addLayout(buttons)
for state, heading in [('success', 'Modèle disponible'), ('busy', 'Vérification en cours'), ('warning', 'Une action est nécessaire'), ('error', 'Connexion impossible')]:
    status = VerificationStatus()
    status.set_status(state, heading, 'Les informations et les actions gardent la même hiérarchie.')
    layout.addWidget(status)
menu = Menu()
menu.addAction('Corriger')
submenu = menu.addMenu('Reformuler')
submenu.addAction('Ton professionnel')
submenu.addAction('Ton chaleureux')
nested = submenu.addMenu('Langue')
group = QActionGroup(nested)
group.setExclusive(True)
for language in ('Français', 'Anglais'):
    action = nested.addAction(language)
    action.setCheckable(True)
    group.addAction(action)
    action.setChecked(language == 'Français')
menu.addSeparator()
menu.addAction('Aucune sélection').setEnabled(False)
menu.addAction('Mode personnalisé…')
loading = SimpleLoadingIndicator('Traitement en cours…')
dictation = RecordingDialog(engine='OpenAI', local=False)

for theme in ('light', 'dark'):
    ThemeManager.apply_theme(app, theme)
    window.resize(600, 830)
    window.show()
    field.selectAll()
    render(window, f'{theme}-controls.png')
    combo.showPopup()
    render(combo.view().window(), f'{theme}-dropdown.png')
    combo.hidePopup()
    editable.showPopup()
    render(editable.view().window(), f'{theme}-editable-dropdown.png')
    editable.hidePopup()
    menu.popup(QPoint(50, 50))
    menu.setActiveAction(submenu.menuAction())
    submenu.popup(QPoint(320, 50))
    submenu.setActiveAction(nested.menuAction())
    nested.popup(QPoint(600, 50))
    for widget, name in ((menu, 'menu'), (submenu, 'submenu'), (nested, 'nested-menu')):
        render(widget, f'{theme}-{name}.png')
    nested.hide()
    submenu.hide()
    menu.hide()
    loading.show()
    render(loading, f'{theme}-loading.png')
    loading.hide()
    dictation.set_recording()
    dictation.set_transcript('Bonjour Camille, merci pour ton retour.')
    dictation.show()
    render(dictation, f'{theme}-dictation.png')
    dictation.hide()
    print('Rendered controls:', theme)

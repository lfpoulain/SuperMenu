"""Regressions for transient feedback, error display and plain-text fields."""

import gc
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QTextEdit

from supermenu_core.ui.controls import PlainTextEdit
from supermenu_core.ui.loading_indicator import SimpleLoadingIndicator
from supermenu_core.ui.prompt_dialog import PromptDialog
from supermenu_core.ui.response_window import BaseResponseWindow
from supermenu_core.ui.safe_dialogs import MAX_MESSAGE_LENGTH, SafeDialogs
from supermenu_core.ui.text_prompt_form import TextPromptForm


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _indicators(message):
    return [
        widget
        for widget in QApplication.topLevelWidgets()
        if isinstance(widget, SimpleLoadingIndicator)
        and widget.label.text() == message
    ]


def test_dropped_indicator_stays_visible_until_its_timer_closes_it(app):
    # Callers such as "Aucun texte sélectionné" ignore the returned object.
    SimpleLoadingIndicator.show_near_cursor("Indicateur abandonné", duration_ms=80)
    gc.collect()
    app.processEvents()
    assert [w.isVisible() for w in _indicators("Indicateur abandonné")] == [True]
    QTest.qWait(200)
    gc.collect()
    assert _indicators("Indicateur abandonné") == []


def test_final_indicator_message_survives_the_request_being_forgotten(app):
    pending = {"request": SimpleLoadingIndicator.show_near_cursor("En attente")}
    indicator = pending.pop("request")
    indicator.set_message("✅ Réponse reçue et insérée")
    QTimer.singleShot(80, indicator.close)
    del indicator
    gc.collect()
    app.processEvents()
    assert [w.isVisible() for w in _indicators("✅ Réponse reçue et insérée")] == [True]
    QTest.qWait(200)
    gc.collect()
    assert _indicators("✅ Réponse reçue et insérée") == []
    assert not SimpleLoadingIndicator._visible_indicators


def test_kept_indicator_can_be_shown_again_after_closing(app):
    indicator = SimpleLoadingIndicator("Vérification des mises à jour...")
    indicator.show()
    indicator.close()
    indicator.show()
    QTest.qWait(20)
    assert indicator.isVisible()
    assert indicator in SimpleLoadingIndicator._visible_indicators
    indicator.close()
    QTest.qWait(20)
    assert indicator not in SimpleLoadingIndicator._visible_indicators
    assert indicator.label.textFormat() == Qt.TextFormat.PlainText


class _Inserter:
    def __init__(self, calls):
        self.calls = calls

    def insert_text_async(self, text, target, callback):
        self.calls.append((text, target))
        callback(True, "")


class _Window(BaseResponseWindow):
    def __init__(self):
        super().__init__()
        self.inserted = []

    def _create_text_inserter(self):
        return _Inserter(self.inserted)


def test_error_is_shown_as_failure_and_cannot_be_inserted(app):
    window = _Window()
    window.store_request("Corrige", "texte")
    window.set_loading(True)
    error = 'Erreur: Erreur 401: {"error": "invalid_api_key"}'
    window.set_error(error)
    window.set_loading(False)
    assert window.has_error
    assert window.response_text.toPlainText() == error
    assert "Terminé" not in window.status_label.text()
    assert window.status_label.property("status") == "error"
    assert not window.write_button.isEnabled()
    assert window.copy_button.isEnabled() and window.retry_button.isEnabled()
    window.show()
    window.write_response()
    QTest.qWait(150)
    assert window.inserted == []
    assert window._pending_paste_text is None
    window.copy_response()
    assert QApplication.clipboard().text() == error
    window.close()


def test_retry_after_error_restores_a_normal_insertable_answer(app):
    window = _Window()
    window.store_request("Corrige", "texte")
    window.set_error("Erreur: réseau indisponible")
    window.retry_request()
    assert not window.has_error
    window.set_response("Texte corrigé")
    window.set_loading(False)
    assert window.status_label.text() == "✅ Terminé"
    assert window.write_button.isEnabled()
    window.write_response()
    QTest.qWait(200)
    assert window.inserted == [("Texte corrigé", None)]
    window.close()


def test_response_window_status_text_is_never_rich_text(app):
    window = _Window()
    window.set_status("<b>Correction</b> en cours…")
    assert window.response_text.toPlainText() == "<b>Correction</b> en cours…"
    assert window.status_label.textFormat() == Qt.TextFormat.PlainText
    window.close()


def test_safe_dialogs_show_server_html_as_truncated_plain_text(app):
    instance = SafeDialogs.get_instance()
    body = (
        'Erreur 502: <html><body><a href="https://example.invalid">'
        "Connectez-vous</a></body></html>" + "x" * (MAX_MESSAGE_LENGTH + 50)
    )
    SafeDialogs.show_critical("Erreur de traitement", body)
    app.processEvents()
    box = instance._open_dialogs[-1]
    try:
        assert box.textFormat() == Qt.TextFormat.PlainText
        assert box.text().startswith("Erreur 502: <html><body><a href=")
        assert len(box.text()) == MAX_MESSAGE_LENGTH + 1
        assert box.text().endswith("…")
        label = box.findChild(QLabel, "qt_msgbox_label")
        assert label.textFormat() == Qt.TextFormat.PlainText
    finally:
        box.done(0)
        app.processEvents()
    assert box not in instance._open_dialogs


def test_short_dialog_messages_are_unchanged(app):
    instance = SafeDialogs.get_instance()
    message = "La fenêtre ou le champ cible a changé.\nLa réponse n'a pas été collée."
    SafeDialogs.show_information("Insertion annulée", message)
    app.processEvents()
    box = instance._open_dialogs[-1]
    try:
        assert box.text() == message
        assert box.icon() == QMessageBox.Icon.Information
    finally:
        box.done(0)
        app.processEvents()


def test_custom_prompt_preview_shows_the_exact_selected_text(app):
    selected = "<b>bold</b> and <script>alert(1)</script>tail"
    dialog = PromptDialog(selected)
    previews = [
        editor for editor in dialog.findChildren(QTextEdit) if editor.isReadOnly()
    ]
    assert [editor.toPlainText() for editor in previews] == [selected]
    dialog.deleteLater()


@pytest.mark.parametrize(
    "instruction",
    [
        "Encadre chaque terme technique avec <code> et </code>.\nRenvoie le texte.",
        "<b>gras</b> obligatoire\nLigne 2",
        "Garde <p>…</p> et <br> tels quels",
        "a < b and c > d",
        "Corrige l’orthographe et la grammaire du texte suivant.",
    ],
)
def test_text_prompt_instruction_round_trips_as_plain_text(app, instruction):
    form = TextPromptForm(settings=SimpleNamespace())
    assert isinstance(form.instruction, PlainTextEdit)
    # The Windows adapter loads prompts with setText().
    form.instruction.setText(instruction)
    assert form.instruction.toPlainText() == instruction
    form.instruction.setPlainText(instruction)
    assert form.instruction.toPlainText() == instruction
    assert not form.instruction.acceptRichText()
    form.deleteLater()

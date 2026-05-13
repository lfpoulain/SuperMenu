import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.ui.response_window import ResponseWindow
from src.utils.safe_dialogs import SafeDialogs


def _app():
    return QApplication.instance() or QApplication([])


def test_safe_dialog_methods_are_qt_slots():
    _app()
    instance = SafeDialogs.get_instance()
    meta = instance.metaObject()

    assert meta.indexOfMethod("_show_information_impl(QString,QString)") != -1
    assert meta.indexOfMethod("_show_warning_impl(QString,QString)") != -1
    assert meta.indexOfMethod("_show_critical_impl(QString,QString)") != -1


def test_response_window_masks_thinking_when_no_final_answer():
    _app()
    window = ResponseWindow()

    window.set_response("<think>raisonnement seulement</think>")

    assert "Aucune reponse finale" in window.response_text.toPlainText()
    window.toggle_thinking_visibility()
    assert "raisonnement seulement" in window.response_text.toPlainText()

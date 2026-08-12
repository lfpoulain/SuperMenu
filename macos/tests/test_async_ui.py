from PySide6.QtWidgets import QApplication

from src.config.settings import Settings
from src.utils.context_menu import ContextMenuManager


def test_custom_prompt_dialog_completes_asynchronously(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    manager = ContextMenuManager(
        Settings(config_path=str(tmp_path / "settings.ini"))
    )
    calls = []
    monkeypatch.setattr(
        manager,
        "_prepare_response_window",
        lambda status, prompt, content, target: calls.append(
            ("prepare", status, prompt, content, target)
        ),
    )
    monkeypatch.setattr(
        manager,
        "_send_request",
        lambda prompt, content, target=None: calls.append(
            ("send", prompt, content, target)
        ),
    )
    target = object()

    manager._handle_custom("texte sélectionné", target)
    dialog = manager._prompt_dialog

    assert dialog is not None
    dialog.prompt_input.setPlainText("Reformule")
    dialog.accept_prompt()
    app.processEvents()

    assert manager._prompt_dialog is None
    assert any(call[0] == "prepare" for call in calls)
    assert ("send", "Reformule", "texte sélectionné", target) in calls
    manager.close()

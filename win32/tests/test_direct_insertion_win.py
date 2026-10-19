"""Direct insertion on Windows: a refused paste never loses the answer."""

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.utils.context_menu import ContextMenuManager


def _app():
    return QApplication.instance() or QApplication([])


class FakeSettings:
    def get_ai_provider(self):
        return "openai"

    def get_api_key(self):
        return "key"

    def get_use_custom_endpoint(self):
        return False

    def get_custom_endpoint(self):
        return ""

    def get_custom_endpoint_type(self):
        return "ollama"

    def get_custom_model(self):
        return ""

    def get_model(self):
        return "gpt-5.6-sol"

    def get_reasoning_effort(self):
        return "none"

    def get_prompts(self):
        return {}

    def get_voice_prompts(self):
        return {}

    def sync(self):
        pass


class FakeIndicator:
    def __init__(self):
        self.messages = []

    def set_message(self, message):
        self.messages.append(message)

    def move_near_cursor(self):
        pass

    def close(self):
        pass


def _manager(monkeypatch, *, inserted):
    _app()
    manager = ContextMenuManager(FakeSettings())
    env = SimpleNamespace(
        presented=[], responses=[], stored=[], dialogs=[], insertions=[],
        copies=[], indicator=FakeIndicator(),
    )
    window = manager.response_window
    window.present = lambda: env.presented.append(True)
    real_set_response = window.set_response
    # The real set_response runs: it rewrites the status and the title.
    window.set_response = lambda text: (env.responses.append(text), real_set_response(text))
    window.set_loading = lambda _value: None
    window.store_request = lambda *args: env.stored.append(args)
    monkeypatch.setattr(manager.api_client, "send_request", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "src.utils.context_menu.SimpleLoadingIndicator.show_near_cursor",
        lambda *_args, **_kwargs: env.indicator,
    )
    monkeypatch.setattr(
        "src.utils.context_menu.SafeDialogs.show_information",
        lambda title, message: env.dialogs.append((title, message)),
    )
    monkeypatch.setattr(
        "src.utils.context_menu.TextInserter.insert_text",
        lambda _self, text, target=None: env.insertions.append((text, target)) or inserted,
    )
    monkeypatch.setattr(
        "src.utils.context_menu.ClipboardManager.set_clipboard_text_safe",
        lambda text, transient=False: env.copies.append((text, transient)) or True,
    )
    monkeypatch.setattr("src.utils.context_menu.QTimer.singleShot", lambda *_args: None)
    return manager, env


def test_refused_direct_insertion_keeps_the_answer_in_the_response_window(monkeypatch):
    manager, env = _manager(monkeypatch, inserted=False)
    target = object()
    model_target = {"provider": "custom", "model": "tiny", "device": None}

    request_id = manager._send_request(
        "Corrige :", "texte sélectionné", True, target=target, model_target=None,
        reasoning_mode="default",
    )
    manager._pending_requests[request_id]["model_target"] = model_target
    manager.on_request_finished_scoped(request_id, "réponse générée", True, target)

    assert env.insertions == [("réponse générée", target)]
    assert env.responses == ["réponse générée"]
    assert env.presented == [True]
    # « Réessayer » relance la même requête sur le même modèle.
    assert env.stored == [("Corrige :", "texte sélectionné")]
    assert manager.response_window.last_model_target == model_target
    assert manager.response_window.paste_target is target
    assert env.copies == []
    assert env.indicator.messages[-1] == "⚠️ Insertion annulée"
    # The window says the answer was not pasted, never « ✅ Terminé ».
    window = manager.response_window
    assert window.status_label.text() == "⚠️ Insertion annulée — réponse conservée"
    assert window.status_label.property("status") == "warning"
    assert window.final_response == "réponse générée"
    assert window.write_button.isEnabled()
    # No extra box: it would end up below the topmost response window.
    assert env.dialogs == []
    assert request_id not in manager._pending_requests
    manager.close()


def test_direct_request_without_target_is_never_pasted_into_the_current_window(monkeypatch):
    manager, env = _manager(monkeypatch, inserted=True)

    request_id = manager._send_request("Réponds :\n\ndictée", "", True, target=None)
    manager.on_request_finished_scoped(request_id, "réponse vocale", True, None)

    assert env.insertions == []
    assert env.responses == ["réponse vocale"]
    assert env.stored == [("Réponds :\n\ndictée", "")]
    assert manager.response_window.paste_target is None
    assert manager.response_window.status_label.text() == "⚠️ Insertion annulée — réponse conservée"
    assert env.dialogs == []
    manager.close()


def test_refused_answer_never_replaces_an_answer_shown_in_the_window(monkeypatch):
    manager, env = _manager(monkeypatch, inserted=False)
    window = manager.response_window
    shown_id = manager._send_request("Explique :", "texte A", False)
    manager.on_request_finished_scoped(shown_id, "réponse A", False, None)
    # The user reads answer A while the direct request B is generated.
    monkeypatch.setattr(window, "isVisible", lambda: True)
    direct_id = manager._send_request("Corrige :", "texte B", True, target=object())

    manager.on_request_finished_scoped(direct_id, "réponse B", True, None)

    assert env.copies == [("réponse B", False)]
    assert env.responses == ["réponse A"]
    assert window.final_response == "réponse A"
    assert window.response_text.toPlainText() == "réponse A"
    # « Réessayer » still relaunches A.
    assert env.stored == []
    assert window.status_label.text() == "✅ Terminé"
    assert len(env.dialogs) == 1 and "presse-papiers" in env.dialogs[0][1]
    manager.close()


def test_refused_answer_replaces_an_error_or_a_hidden_window(monkeypatch):
    manager, env = _manager(monkeypatch, inserted=False)
    window = manager.response_window
    monkeypatch.setattr(window, "isVisible", lambda: True)
    window.set_error("Erreur: délai dépassé")
    direct_id = manager._send_request("Corrige :", "texte", True, target=object())

    manager.on_request_finished_scoped(direct_id, "réponse", True, None)

    assert env.copies == []
    assert env.responses == ["réponse"]
    assert env.dialogs == []
    manager.close()


def test_refused_answer_is_copied_when_the_window_awaits_another_answer(monkeypatch):
    manager, env = _manager(monkeypatch, inserted=False)
    waiting_id = manager._send_request("Explique :", "texte", False)
    direct_id = manager._send_request("Corrige :", "texte", True, target=object())

    manager.on_request_finished_scoped(direct_id, "réponse directe", True, None)

    assert env.copies == [("réponse directe", False)]
    assert env.responses == []
    assert env.presented == []
    assert "presse-papiers" in env.dialogs[0][1]
    assert waiting_id in manager._pending_requests
    manager.close()


def test_successful_direct_insertion_is_unchanged(monkeypatch):
    manager, env = _manager(monkeypatch, inserted=True)
    target = object()

    request_id = manager._send_request("Corrige :", "texte", True, target=target)
    manager.on_request_finished_scoped(request_id, "réponse", True, target)

    assert env.insertions == [("réponse", target)]
    assert env.responses == [] and env.presented == [] and env.dialogs == []
    assert env.indicator.messages[-1] == "✅ Réponse reçue et insérée"
    manager.close()

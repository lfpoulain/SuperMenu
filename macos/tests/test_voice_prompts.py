import json

import pytest
from PySide6.QtWidgets import QApplication

from src.config.settings import Settings
from src.ui.main_window import MainWindow
from src.utils import context_menu
from supermenu_core.audio import settings as speech_settings
from supermenu_core.audio.backends import SpeechBackend
from supermenu_core.ui.voice_prompt_editor import VoicePromptEditor


class Backend(SpeechBackend):
    def start(self):
        pass

    def cancel(self):
        pass


@pytest.mark.parametrize("provider", ["openai", "apple"])
@pytest.mark.parametrize("direct", [False, True])
def test_voice_prompt_only_dispatches_final_text_with_original_selection_and_target(
    tmp_path, monkeypatch, provider, direct
):
    from src.audio import speech_backend

    app = QApplication.instance() or QApplication([])
    settings = Settings(str(tmp_path / "settings.ini"))
    settings.set_speech_provider(provider)
    settings.update_voice_prompt(
        "reply",
        "Répondre",
        "Rédige une réponse",
        "Rédaction",
        direct,
        1,
        True,
        "selected_prompt_transcription",
    )
    backend = Backend()
    monkeypatch.setattr(
        speech_settings,
        "speech_options",
        lambda settings: {"provider": settings.get_speech_provider()},
    )
    monkeypatch.setattr(speech_backend, "create_speech_backend", lambda *_args: backend)
    monkeypatch.setattr(context_menu, "activate_current_application", lambda: True)
    manager = context_menu.ContextMenuManager(settings)
    target, requests, prepared = object(), [], []
    monkeypatch.setattr(
        manager,
        "_send_request",
        lambda *args, **kwargs: requests.append((args, kwargs)),
    )
    monkeypatch.setattr(
        manager, "_prepare_response_window", lambda *args: prepared.append(args)
    )
    manager._start_voice_prompt(
        settings.get_voice_prompt("reply"), "Message de Camille", target
    )
    backend.transcript.emit("Je suis disponible")
    assert not requests
    # Editing the stored prompt during capture must not mutate the active one.
    settings.update_voice_prompt("reply", "Autre", "AUTRE", "Autre")
    backend.completed.emit("Je suis disponible demain.")
    assert len(requests) == 1
    args, options = requests[0]
    assert args == (
        "Texte sélectionné: Message de Camille\n\nRédige une réponse\n\nTexte transcrit: Je suis disponible demain.",
        "",
    )
    assert options["target"] is target and options["insert_directly"] is direct
    assert options["include_reasoning"] is (False if direct else None)
    assert bool(prepared) is not direct
    if prepared:
        assert prepared[0][-1] is target
    manager.close()
    assert app is not None


def test_cancelled_voice_prompt_never_sends_text_to_ai(tmp_path, monkeypatch):
    from src.audio import speech_backend

    QApplication.instance() or QApplication([])
    backend = Backend()
    monkeypatch.setattr(speech_backend, "create_speech_backend", lambda *_args: backend)
    monkeypatch.setattr(context_menu, "activate_current_application", lambda: True)
    manager = context_menu.ContextMenuManager(Settings(str(tmp_path / "settings.ini")))
    calls = []
    monkeypatch.setattr(
        manager, "_send_request", lambda *args, **kwargs: calls.append(args)
    )
    manager._start_voice_prompt({"prompt": "Résume"}, "", object())
    manager._dictation.recording_dialog.close()
    backend.completed.emit("Résultat tardif")
    assert calls == []
    manager.close()


def test_editor_captures_selection_asynchronously_before_starting_voice(
    tmp_path, monkeypatch
):
    QApplication.instance() or QApplication([])
    settings = Settings(str(tmp_path / "settings.ini"))
    settings.update_voice_prompt(
        "reply", "Répondre", "Réponds", "Rédaction", False, 1, True
    )
    deliveries, captures, starts = [], [], []
    target = object()

    class Reader:
        def read_async(self, captured, callback):
            assert captured is target
            deliveries.append(callback)

    def capture(**kwargs):
        captures.append(kwargs)
        return target

    monkeypatch.setattr(context_menu.PasteTarget, "capture", capture)
    manager = context_menu.ContextMenuManager(settings, selection_reader=Reader())
    monkeypatch.setattr(
        manager, "_start_voice_prompt", lambda *args: starts.append(args)
    )
    manager.run_voice_prompt("reply", from_ui=True)
    assert captures == [{"fall_back_to_last_known": True}]
    assert not starts
    deliveries[0]("Message sélectionné")
    assert starts[0][1:] == ("Message sélectionné", target)
    assert not manager._selection_pending
    manager.close()


def test_mac_voice_submenu_dispatches_the_selected_prompt(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(context_menu, "activate_current_application", lambda: True)
    monkeypatch.setattr(context_menu, "current_application_is_active", lambda: True)
    manager = context_menu.ContextMenuManager(Settings(str(tmp_path / "settings.ini")))
    calls, target = [], object()
    monkeypatch.setattr(
        manager, "_start_voice_prompt", lambda *args: calls.append(args)
    )
    manager._present_menu("Sélection conservée", target)
    menu = manager._active_menu
    voice = next(action.menu() for action in menu.actions() if action.text() == "Voix")
    action = next(
        action
        for action in voice.actions()
        if action.data() == ("voice_prompt", "resumer_vocal")
    )
    action.trigger()
    assert len(calls) == 1
    assert calls[0][0]["name"] == "Résumer"
    assert calls[0][1:] == ("Sélection conservée", target)
    app.processEvents()
    manager.close()


def test_custom_voice_prompt_waits_for_dialog_acceptance(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(context_menu, "activate_current_application", lambda: True)
    manager = context_menu.ContextMenuManager(Settings(str(tmp_path / "settings.ini")))
    calls, target = [], object()
    monkeypatch.setattr(
        manager, "_start_voice_prompt", lambda *args: calls.append(args)
    )
    manager._handle_custom("", target, voice=True)
    assert not calls
    manager._prompt_dialog.reject()
    assert not calls
    manager._handle_custom("", target, voice=True)
    manager._prompt_dialog.prompt_input.setPlainText("Traduis ma dictée en anglais")
    manager._prompt_dialog.accept_prompt()
    assert len(calls) == 1
    prompt, selection, captured_target = calls[0]
    assert prompt["prompt"] == "Traduis ma dictée en anglais"
    assert not prompt["insert_directly"] and not selection
    assert captured_target is target
    manager.close()


def test_voice_editor_uses_macos_target_and_permission_tab_still_opens_settings(
    tmp_path, monkeypatch
):
    QApplication.instance() or QApplication([])
    settings = Settings(str(tmp_path / "settings.ini"))
    window = MainWindow(settings)
    assert isinstance(window.voice_prompt_editor, VoicePromptEditor)
    assert (
        window.tabs.tabText(window.tabs.indexOf(window.voice_prompt_editor)) == "Voix"
    )
    monkeypatch.setattr(window, "show_main_window", lambda: None)
    window.show_permission_setup()
    assert window.tabs.currentWidget() is window.settings_tab
    assert (
        window.settings_panel.keys[window.settings_panel.navigation.currentRow()]
        == "app"
    )
    window.close()


def test_mac_import_preserves_voice_library_when_given_old_mac_file(tmp_path):
    settings = Settings(str(tmp_path / "settings.ini"))
    before = settings.get_voice_prompts()
    file = tmp_path / "old-mac.json"
    file.write_text(
        json.dumps({"schema_version": 1, "prompts": settings.get_prompts()}),
        encoding="utf-8",
    )
    settings.import_prompts(str(file))
    assert settings.get_voice_prompts() == before
    settings.export_prompts(str(file))
    exported = json.loads(file.read_text(encoding="utf-8"))
    assert exported["voice_prompts"] == before
    assert exported["text_prompts"] == settings.get_prompts()

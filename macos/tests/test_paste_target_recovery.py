"""Paste target recovery: the « Insérer le texte » button after a refused
direct answer, slow applications, the error box and voice prompts."""

import os
import time

import pytest
from PySide6.QtWidgets import QApplication

import src.utils.context_menu as context_menu_module
from src.config.settings import Settings
from src.utils import accessibility_text
from src.utils import text_inserter as text_inserter_module
from src.utils import window_target
from src.utils.context_menu import ContextMenuManager
from src.utils.key_events import KeyEventPoster
from src.utils.selection import (
    COPY_MAX_POLLS,
    SLOW_ACCESSIBILITY_MS,
    SelectionReader,
)
from src.utils.text_inserter import TextInserter

from tests.fake_key_api import FakeQuartzKeyAPI


class QueuedScheduler:
    def __init__(self):
        self.callbacks = []

    def __call__(self, _delay, callback):
        self.callbacks.append(callback)

    def drain(self, limit=400):
        while self.callbacks and limit:
            limit -= 1
            self.callbacks.pop(0)()


@pytest.fixture
def manager(tmp_path):
    QApplication.instance() or QApplication([])
    value = ContextMenuManager(Settings(config_path=str(tmp_path / "settings.ini")))
    yield value
    value.close()


# --- A real target whose focused window can change -------------------------


class _Application:
    def __init__(self, process_id, bundle="com.example.mail", name="Mail"):
        self._process_id = process_id
        self._bundle = bundle
        self._name = name

    def processIdentifier(self):
        return self._process_id

    def bundleIdentifier(self):
        return self._bundle

    def localizedName(self):
        return self._name

    def isTerminated(self):
        return False

    def activateWithOptions_(self, _options):
        return True


@pytest.fixture
def mail(monkeypatch):
    """Mail in front with window W1; tests move the focus and the foreground."""
    window_target.PasteTarget.forget_last_known()
    state = {
        "front": _Application(4321),
        "window": "W1",
    }
    monkeypatch.setattr(
        window_target, "_frontmost_application", lambda: state["front"]
    )
    monkeypatch.setattr(
        window_target,
        "focused_window_of_application",
        lambda _pid: state["window"],
    )
    monkeypatch.setattr(
        window_target,
        "same_accessibility_element",
        lambda first, second: first == second,
    )
    monkeypatch.setattr(
        window_target,
        "NSRunningApplication",
        type(
            "FakeRunningApplication",
            (),
            {
                "runningApplicationWithProcessIdentifier_": staticmethod(
                    lambda _pid: _Application(4321)
                )
            },
        ),
    )
    yield state
    window_target.PasteTarget.forget_last_known()


def _stub_clipboard(monkeypatch):
    events = []
    monkeypatch.setattr(
        text_inserter_module.ClipboardManager,
        "capture_snapshot",
        lambda: "snapshot",
    )
    monkeypatch.setattr(
        text_inserter_module.ClipboardManager,
        "set_clipboard_text_safe",
        lambda text: events.append(("set", text)) or True,
    )
    monkeypatch.setattr(
        text_inserter_module.ClipboardManager,
        "restore_if_unchanged",
        lambda snapshot, text: events.append(("restore", snapshot, text)),
    )
    return events


def _insert(target):
    scheduler = QueuedScheduler()
    api = FakeQuartzKeyAPI()
    results = []
    TextInserter(keys=KeyEventPoster(api=api), scheduler=scheduler).insert_text_async(
        "réponse", target, lambda *args: results.append(args)
    )
    scheduler.drain()
    return results, api.posted


class RecordingResponseWindow:
    def __init__(self):
        self.paste_target = None
        self.responses = []
        self.last_reasoning_mode = "default"
        self.last_model_target = {}

    def set_status(self, _status):
        pass

    def set_trigger_position(self, _position):
        pass

    def set_paste_target(self, target):
        self.paste_target = target

    def store_request(self, _prompt, _content):
        pass

    def present(self):
        pass

    def set_response(self, text):
        self.responses.append(text)

    def set_loading(self, _loading):
        pass

    def close(self):
        pass


# --- « Écrire » checks the application only, direct insertion the window ---


def test_write_button_pastes_into_the_window_the_user_opened(
    manager, mail, monkeypatch
):
    _stub_clipboard(monkeypatch)
    target = window_target.PasteTarget.capture()
    assert target.focused_window == "W1"
    manager.response_window.close()
    manager.response_window = RecordingResponseWindow()

    manager._prepare_response_window("Réponse", "Réponds", "Message", target)
    # The user clicks « Répondre » in Mail: a compose window W2 takes focus.
    mail["window"] = "W2"

    written = manager.response_window.paste_target
    assert written == target
    results, posted = _insert(written)
    assert results == [(True, "")]
    assert posted

    # The direct insertion, which nobody confirms, still refuses W2.
    results, posted = _insert(target)
    assert results == [(False, "window_changed")]
    assert posted == []


def test_a_refused_direct_answer_can_then_be_written_on_purpose(
    manager, mail, monkeypatch
):
    _stub_clipboard(monkeypatch)
    target = window_target.PasteTarget.capture()
    manager.response_window.close()
    manager.response_window = RecordingResponseWindow()
    mail["window"] = "W2"

    kept = manager._keep_refused_direct_response(
        {"prompt": "Corrige", "content": "texte"}, "réponse", target
    )

    assert kept == "window"
    results, _posted = _insert(manager.response_window.paste_target)
    assert results == [(True, "")]


def test_targets_without_a_window_check_are_passed_through(manager):
    manager.response_window.close()
    manager.response_window = RecordingResponseWindow()
    plain = object()

    manager._prepare_response_window("Réponse", "Réponds", "Message", plain)
    assert manager.response_window.paste_target is plain

    unknown = window_target.PasteTarget(process_id=42)
    assert unknown.application_only() is unknown


# --- A remembered target never keeps a stale window ------------------------


def test_a_last_known_target_only_verifies_the_application(mail):
    remembered = window_target.PasteTarget.remember_frontmost()
    assert remembered.focused_window == "W1"

    # The user selects text in another window, then opens SuperMenu.
    mail["window"] = "W2"
    mail["front"] = _Application(os.getpid(), "com.supermenu.macos", "SuperMenu")

    fallback = window_target.PasteTarget.capture(fall_back_to_last_known=True)
    assert fallback == remembered
    assert fallback.focused_window is None

    # Mail is reactivated: the selection and the paste both happen in W2.
    mail["front"] = _Application(4321)
    assert fallback.is_current() is True
    assert fallback.focused_window_matches() is True


def test_a_fresh_capture_still_records_the_focused_window(mail):
    window_target.PasteTarget.remember_frontmost()
    mail["window"] = "W2"

    target = window_target.PasteTarget.capture()

    assert target.focused_window == "W2"
    mail["window"] = "W3"
    assert target.focused_window_matches() is False


# --- A busy application keeps its selection ---------------------------------


def test_the_accessibility_ceiling_leaves_room_for_busy_applications():
    assert 1.0 <= accessibility_text.AX_MESSAGING_TIMEOUT_S < 6


class SlowAccessibility:
    def __init__(self, delay_s):
        self.delay_s = delay_s

    def selected_text(self):
        time.sleep(self.delay_s)
        return None


class LateClipboard:
    """The copy only lands after a number of polls."""

    def __init__(self, polls_before_copy, text):
        self.polls_before_copy = polls_before_copy
        self.text = text
        self.current = ""
        self.reads = 0
        self.events = []

    def capture_snapshot(self):
        return "snapshot"

    def set_clipboard_text_safe(self, text):
        self.current = text
        return True

    def get_clipboard_text_safe(self):
        self.reads += 1
        if self.reads > self.polls_before_copy:
            return self.text
        return self.current

    def restore_if_unchanged(self, snapshot, expected):
        self.events.append(("restore", snapshot, expected))
        return True


class FrontTarget:
    def is_current(self):
        return True

    def request_activation(self, force=False):
        return True


def _read(accessibility, clipboard):
    scheduler = QueuedScheduler()
    results = []
    SelectionReader(
        keys=KeyEventPoster(api=FakeQuartzKeyAPI()),
        scheduler=scheduler,
        clipboard=clipboard,
        accessibility=accessibility,
    ).read_async(FrontTarget(), results.append)
    scheduler.drain()
    return results


def test_a_slow_accessibility_answer_gives_the_copy_more_time():
    late = COPY_MAX_POLLS + 20
    clipboard = LateClipboard(late, "sélection tardive")

    results = _read(SlowAccessibility(SLOW_ACCESSIBILITY_MS / 1000 + 0.05), clipboard)

    assert results == ["sélection tardive"]
    # The late copy is the one restored, not the sentinel it replaced.
    assert clipboard.events[-1] == ("restore", "snapshot", "sélection tardive")


def test_a_healthy_application_keeps_the_short_copy_wait():
    clipboard = LateClipboard(COPY_MAX_POLLS + 20, "jamais attendue")

    results = _read(SlowAccessibility(0), clipboard)

    assert results == [""]
    assert clipboard.reads == COPY_MAX_POLLS + 1


# --- The error box only returns to a target the user had not left ---------


class Target:
    def __init__(self, current):
        self.current = current
        self.activations = 0

    def is_current(self):
        return self.current

    def request_activation(self, force=False):
        self.activations += 1
        return True


def _direct_error(manager, monkeypatch, target, *, supermenu_active):
    shown = []
    monkeypatch.setattr(
        context_menu_module.SafeDialogs,
        "show_critical",
        lambda title, message, parent=None, **kwargs: shown.append(kwargs),
    )
    monkeypatch.setattr(
        context_menu_module,
        "current_application_is_active",
        lambda: supermenu_active,
    )
    manager._pending_requests["directe"] = {
        "client": manager.api_client,
        "insert_directly": True,
        "target": target,
        "indicator": None,
    }
    manager.on_request_error_scoped("directe", "délai dépassé")
    assert len(shown) == 1
    return shown[0].get("on_closed")


def test_the_error_box_leaves_the_user_in_the_application_they_moved_to(
    manager, monkeypatch
):
    target = Target(current=False)

    on_closed = _direct_error(manager, monkeypatch, target, supermenu_active=False)

    assert on_closed is None
    assert target.activations == 0


@pytest.mark.parametrize(
    "current, supermenu_active", [(True, False), (False, True)]
)
def test_the_error_box_returns_to_a_target_the_user_had_not_left(
    manager, monkeypatch, current, supermenu_active
):
    target = Target(current=current)

    on_closed = _direct_error(
        manager, monkeypatch, target, supermenu_active=supermenu_active
    )

    assert target.activations == 0
    on_closed()
    assert target.activations == 1


# --- A direct voice prompt hands the foreground back -----------------------


class RecordingTimer:
    def __init__(self):
        self.scheduled = []

    def singleShot(self, delay, callback):
        self.scheduled.append((delay, callback))


@pytest.mark.parametrize("direct", [True, False])
def test_a_direct_voice_prompt_reactivates_the_target_during_the_call(
    manager, monkeypatch, direct
):
    timer = RecordingTimer()
    monkeypatch.setattr(context_menu_module, "QTimer", timer)
    sessions, prepared = [], []
    monkeypatch.setattr(manager, "_start_voice_session", sessions.append)
    monkeypatch.setattr(
        manager, "_prepare_response_window", lambda *args: prepared.append(args)
    )

    def send(*_args, **_kwargs):
        manager._pending_requests["vocal"] = {
            "client": manager.api_client,
            "insert_directly": direct,
            "target": target,
            "indicator": None,
        }
        return "vocal"

    monkeypatch.setattr(manager, "_send_request", send)
    target = Target(current=False)

    manager._start_voice_prompt(
        {"prompt": "Résume", "insert_directly": direct}, "", target
    )
    sessions[0]("Bonjour")

    restores = [callback for _delay, callback in timer.scheduled]
    if direct:
        assert len(restores) == 1 and not prepared
        restores[0]()
        assert target.activations == 1
    else:
        # The response window takes over: nothing is handed back.
        assert restores == [] and len(prepared) == 1
        assert target.activations == 0


def test_a_voice_prompt_that_failed_at_once_does_not_reactivate(
    manager, monkeypatch
):
    timer = RecordingTimer()
    monkeypatch.setattr(context_menu_module, "QTimer", timer)
    sessions = []
    monkeypatch.setattr(manager, "_start_voice_session", sessions.append)
    # The request failed synchronously: it is no longer pending.
    monkeypatch.setattr(manager, "_send_request", lambda *_a, **_k: "échouée")
    target = Target(current=False)

    manager._start_voice_prompt({"prompt": "Résume", "insert_directly": True}, "", target)
    sessions[0]("Bonjour")

    assert timer.scheduled == []

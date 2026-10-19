"""Window-level paste check and Accessibility safeguards."""

import os

from src.utils import accessibility_text
from src.utils import text_inserter as text_inserter_module
from src.utils import window_target
from src.utils.accessibility_text import AccessibilitySelectionReader
from src.utils.key_events import KeyEventPoster
from src.utils.selection import SelectionReader
from src.utils.text_inserter import TextInserter

from tests.fake_key_api import FakeQuartzKeyAPI


class QueuedScheduler:
    def __init__(self):
        self.callbacks = []

    def __call__(self, _delay, callback):
        self.callbacks.append(callback)

    def drain(self, limit=60):
        while self.callbacks and limit:
            limit -= 1
            self.callbacks.pop(0)()


# --- Selection: the Accessibility fast path only reads the target ---------


class RecordingAccessibility:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def selected_text(self):
        self.calls += 1
        return self.text


class RecordingClipboard:
    def __init__(self, text_after_copy):
        self.events = []
        self.current = ""
        self.text_after_copy = text_after_copy

    def capture_snapshot(self):
        return "snapshot"

    def set_clipboard_text_safe(self, text):
        self.events.append(("set", text))
        self.current = text
        return True

    def get_clipboard_text_safe(self):
        return self.text_after_copy

    def restore_if_unchanged(self, snapshot, expected):
        self.events.append(("restore", snapshot, expected))
        return True


class BackgroundTarget:
    """The application the user came from, behind SuperMenu's own window."""

    def __init__(self):
        self.active = False
        self.activation_requests = []

    def request_activation(self, force=False):
        self.activation_requests.append(force)
        self.active = True
        return True

    def is_current(self):
        return self.active


def test_a_background_target_never_gets_supermenus_own_selection():
    scheduler = QueuedScheduler()
    accessibility = RecordingAccessibility("texte saisi dans SuperMenu")
    clipboard = RecordingClipboard("texte de l’application cible")
    target = BackgroundTarget()
    results = []

    SelectionReader(
        keys=KeyEventPoster(api=FakeQuartzKeyAPI()),
        scheduler=scheduler,
        clipboard=clipboard,
        accessibility=accessibility,
    ).read_async(target, results.append)
    scheduler.drain()

    # The focused element belonged to SuperMenu: it is not even queried.
    assert accessibility.calls == 0
    assert target.activation_requests == [False]
    assert results == ["texte de l’application cible"]


def test_a_frontmost_target_still_uses_the_accessibility_fast_path():
    scheduler = QueuedScheduler()
    accessibility = RecordingAccessibility("texte AX")
    clipboard = RecordingClipboard("jamais lu")
    target = BackgroundTarget()
    target.active = True
    results = []

    SelectionReader(
        keys=KeyEventPoster(api=FakeQuartzKeyAPI()),
        scheduler=scheduler,
        clipboard=clipboard,
        accessibility=accessibility,
    ).read_async(target, results.append)

    assert results == ["texte AX"]
    assert clipboard.events == []
    assert target.activation_requests == []


class FakeAXAPI:
    focused_attribute = "AXFocusedUIElement"
    selected_text_attribute = "AXSelectedText"

    def __init__(self, pid_answer):
        self.pid_answer = pid_answer
        self.queried = []

    def is_available(self):
        return True

    def system_wide_element(self):
        return "system"

    def copy_attribute(self, element, attribute):
        self.queried.append(attribute)
        if attribute == self.focused_attribute:
            return 0, "element"
        return 0, "sélection"

    def element_pid(self, _element):
        if isinstance(self.pid_answer, Exception):
            raise self.pid_answer
        return self.pid_answer


def test_an_element_owned_by_supermenu_is_never_read():
    api = FakeAXAPI((0, os.getpid()))

    assert AccessibilitySelectionReader(api=api).selected_text() is None
    assert api.queried == ["AXFocusedUIElement"]


def test_an_element_owned_by_another_process_is_still_read():
    # Hosted views (open panels, web content) may report another process
    # than the frontmost application: only SuperMenu itself is excluded.
    api = FakeAXAPI((0, os.getpid() + 1))

    assert AccessibilitySelectionReader(api=api).selected_text() == "sélection"


def test_an_unknown_element_owner_keeps_the_previous_behaviour():
    for answer in (None, (-25204, 0), RuntimeError("AXUIElementGetPid")):
        api = FakeAXAPI(answer)
        assert AccessibilitySelectionReader(api=api).selected_text() == "sélection"


# --- Accessibility calls are bounded --------------------------------------


def test_the_system_wide_element_gets_a_messaging_timeout(monkeypatch):
    calls = []
    monkeypatch.setattr(
        accessibility_text,
        "AXUIElementCreateSystemWide",
        lambda: "system",
    )
    monkeypatch.setattr(
        accessibility_text,
        "AXUIElementSetMessagingTimeout",
        lambda element, seconds: calls.append((element, seconds)) or 0,
    )

    assert accessibility_text._AccessibilityAPI.system_wide_element() == "system"
    assert calls == [("system", accessibility_text.AX_MESSAGING_TIMEOUT_S)]
    assert 0 < accessibility_text.AX_MESSAGING_TIMEOUT_S <= 1


def test_a_failing_timeout_binding_never_blocks_the_read(monkeypatch):
    def explode(_element, _seconds):
        raise RuntimeError("AXUIElementSetMessagingTimeout")

    monkeypatch.setattr(accessibility_text, "AXUIElementSetMessagingTimeout", explode)

    accessibility_text.limit_messaging_timeout("system")
    monkeypatch.setattr(accessibility_text, "AXUIElementSetMessagingTimeout", None)
    accessibility_text.limit_messaging_timeout("system")


def test_focused_window_lookup_is_bounded_and_fails_open(monkeypatch):
    timeouts = []
    answers = {"value": (0, "fenêtre")}
    monkeypatch.setattr(
        accessibility_text,
        "AXUIElementCreateApplication",
        lambda pid: f"application-{pid}",
    )
    monkeypatch.setattr(
        accessibility_text,
        "AXUIElementSetMessagingTimeout",
        lambda element, seconds: timeouts.append(element) or 0,
    )
    monkeypatch.setattr(
        accessibility_text,
        "AXUIElementCopyAttributeValue",
        lambda element, attribute, _out: answers["value"],
    )

    assert accessibility_text.focused_window_of_application(42) == "fenêtre"
    assert timeouts == ["application-42"]

    # kAXErrorCannotComplete: the application did not answer in time.
    answers["value"] = (-25204, None)
    assert accessibility_text.focused_window_of_application(42) is None

    monkeypatch.setattr(accessibility_text, "AXUIElementCreateApplication", None)
    assert accessibility_text.focused_window_of_application(42) is None


def test_element_comparison_prefers_cfequal_and_reports_unknowns(monkeypatch):
    monkeypatch.setattr(accessibility_text, "CFEqual", lambda a, b: a == b)
    assert accessibility_text.same_accessibility_element("a", "a") is True
    assert accessibility_text.same_accessibility_element("a", "b") is False
    assert accessibility_text.same_accessibility_element(None, "b") is None

    def explode(_first, _second):
        raise RuntimeError("CFEqual")

    monkeypatch.setattr(accessibility_text, "CFEqual", explode)
    assert accessibility_text.same_accessibility_element("a", "a") is None


# --- Paste target: the window is verified, not only the application ------


class _Frontmost:
    def __init__(self, process_id):
        self._process_id = process_id

    def processIdentifier(self):
        return self._process_id

    def bundleIdentifier(self):
        return "com.example.editor"

    def localizedName(self):
        return "Editor"


def _windows(monkeypatch, focused):
    monkeypatch.setattr(
        window_target,
        "focused_window_of_application",
        lambda _pid: focused["window"],
    )
    monkeypatch.setattr(
        window_target,
        "same_accessibility_element",
        lambda first, second: first == second,
    )


def test_capture_remembers_the_focused_window(monkeypatch):
    window_target.PasteTarget.forget_last_known()
    focused = {"window": "brouillon A"}
    _windows(monkeypatch, focused)
    monkeypatch.setattr(
        window_target,
        "_frontmost_application",
        lambda: _Frontmost(4321),
    )

    target = window_target.PasteTarget.capture()

    assert target.focused_window == "brouillon A"
    assert target.focused_window_matches() is True
    focused["window"] = "brouillon B"
    assert target.focused_window_matches() is False
    window_target.PasteTarget.forget_last_known()


def test_unknown_windows_keep_the_application_level_check(monkeypatch):
    focused = {"window": None}
    _windows(monkeypatch, focused)

    unknown_at_capture = window_target.PasteTarget(process_id=42)
    assert unknown_at_capture.focused_window_matches() is True

    known = window_target.PasteTarget(process_id=42, focused_window="A")
    # Accessibility does not answer any more: the paste is not blocked.
    assert known.focused_window_matches() is True

    monkeypatch.setattr(
        window_target,
        "same_accessibility_element",
        lambda _first, _second: None,
    )
    focused["window"] = "B"
    assert known.focused_window_matches() is True


def test_the_window_is_not_part_of_the_target_identity():
    first = window_target.PasteTarget(42, "com.example", "Ex", focused_window="A")
    second = window_target.PasteTarget(42, "com.example", "Ex", focused_window="B")

    assert first == second
    assert hash(first) == hash(second)
    assert "focused_window" not in repr(first)


class WindowTarget:
    def __init__(self, window_matches=True):
        self.window_matches = window_matches
        self.active = True

    def request_activation(self, force=False):
        return True

    def is_current(self):
        return self.active

    def focused_window_matches(self):
        if isinstance(self.window_matches, Exception):
            raise self.window_matches
        return self.window_matches


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


def test_insertion_is_cancelled_when_another_window_took_focus(monkeypatch):
    clipboard_events = _stub_clipboard(monkeypatch)
    scheduler = QueuedScheduler()
    api = FakeQuartzKeyAPI()
    target = WindowTarget(window_matches=False)
    results = []

    TextInserter(keys=KeyEventPoster(api=api), scheduler=scheduler).insert_text_async(
        "réponse", target, lambda *args: results.append(args)
    )
    scheduler.drain()

    assert results == [(False, "window_changed")]
    # No Command+V reached the other window, and the clipboard is restored.
    assert api.posted == []
    assert clipboard_events[-1] == ("restore", "snapshot", "réponse")


def test_insertion_goes_ahead_when_the_window_check_cannot_answer(monkeypatch):
    _stub_clipboard(monkeypatch)
    for target in (
        WindowTarget(window_matches=True),
        WindowTarget(window_matches=RuntimeError("AX")),
    ):
        scheduler = QueuedScheduler()
        api = FakeQuartzKeyAPI()
        results = []

        TextInserter(
            keys=KeyEventPoster(api=api),
            scheduler=scheduler,
        ).insert_text_async("réponse", target, lambda *args: results.append(args))
        scheduler.drain()

        assert results == [(True, "")]
        assert api.posted

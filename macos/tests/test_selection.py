from src.utils.key_events import KEY_CODE_C, KEY_CODE_COMMAND, KeyEventPoster
from src.utils.selection import SelectionReader

from tests.fake_key_api import FakeQuartzKeyAPI


class QueuedScheduler:
    def __init__(self):
        self.callbacks = []

    def __call__(self, _delay, callback):
        self.callbacks.append(callback)

    def run_next(self):
        self.callbacks.pop(0)()

    def drain(self, limit=50):
        while self.callbacks and limit:
            limit -= 1
            self.run_next()


class FakeClipboard:
    """Stands in for the Qt clipboard, recording the sentinel round trip."""

    def __init__(self, text_after_copy=None):
        self.events = []
        self.current = ""
        self.text_after_copy = text_after_copy

    def capture_snapshot(self):
        self.events.append(("snapshot",))
        return "snapshot"

    def set_clipboard_text_safe(self, text):
        self.events.append(("set", text))
        self.current = text
        return True

    def get_clipboard_text_safe(self):
        if self.text_after_copy is not None:
            return self.text_after_copy
        return self.current

    def restore_if_unchanged(self, snapshot, expected):
        self.events.append(("restore", snapshot, expected))
        return True


class FakeTarget:
    def __init__(self, *, active=False, available=True):
        self.active = active
        self.available = available
        self.activation_requests = []

    def request_activation(self, force=False):
        self.activation_requests.append(force)
        return self.available

    def is_current(self):
        return self.active


def _reader(scheduler, clipboard, api, accessibility=None):
    # The Accessibility fast path is exercised separately; the clipboard tests
    # below pin the fallback that has to keep working when it stays silent.
    return SelectionReader(
        keys=KeyEventPoster(api=api),
        scheduler=scheduler,
        clipboard=clipboard,
        accessibility=accessibility or FakeAccessibility(None),
    )


def test_selection_is_read_without_blocking_the_run_loop():
    scheduler = QueuedScheduler()
    clipboard = FakeClipboard(text_after_copy="texte sélectionné")
    api = FakeQuartzKeyAPI()
    target = FakeTarget(active=True)
    results = []

    _reader(scheduler, clipboard, api).read_async(target, results.append)

    # Nothing is delivered synchronously: every wait is a scheduled turn.
    assert results == []
    scheduler.drain()

    assert results == ["texte sélectionné"]
    assert api.posted == [
        (KEY_CODE_COMMAND, True, api.command_flag),
        (KEY_CODE_C, True, api.command_flag),
        (KEY_CODE_C, False, api.command_flag),
        (KEY_CODE_COMMAND, False, 0),
    ]
    assert ("restore", "snapshot", "texte sélectionné") in clipboard.events


def test_copy_waits_for_the_shortcut_modifiers_to_be_released():
    scheduler = QueuedScheduler()
    clipboard = FakeClipboard(text_after_copy="abc")
    api = FakeQuartzKeyAPI()
    api.held = api.command_flag | api.shift_flag
    target = FakeTarget(active=True)
    results = []

    _reader(scheduler, clipboard, api).read_async(target, results.append)
    scheduler.drain(limit=5)

    # Copying now would reach the target application as Command+Shift+C.
    assert api.posted == []

    api.held = 0
    scheduler.drain()

    assert api.posted[1] == (KEY_CODE_C, True, api.command_flag)
    assert results == ["abc"]


def test_sentinel_means_the_user_had_selected_nothing():
    scheduler = QueuedScheduler()
    clipboard = FakeClipboard()
    target = FakeTarget(active=True)
    results = []

    _reader(scheduler, clipboard, FakeQuartzKeyAPI()).read_async(
        target,
        results.append,
    )
    scheduler.drain()

    assert results == [""]
    sentinel = clipboard.events[1][1]
    assert sentinel.startswith("__SUPERMENU_EMPTY_SELECTION_")
    assert ("restore", "snapshot", sentinel) in clipboard.events


def test_activation_is_polled_rather_than_slept_through():
    scheduler = QueuedScheduler()
    clipboard = FakeClipboard(text_after_copy="abc")
    target = FakeTarget(active=False)
    results = []

    _reader(scheduler, clipboard, FakeQuartzKeyAPI()).read_async(
        target,
        results.append,
    )
    scheduler.run_next()
    scheduler.run_next()

    assert results == []
    target.active = True
    scheduler.drain()

    assert results == ["abc"]


def test_a_target_that_never_activates_gives_up_without_touching_the_clipboard():
    scheduler = QueuedScheduler()
    clipboard = FakeClipboard()
    target = FakeTarget(active=False)
    results = []

    _reader(scheduler, clipboard, FakeQuartzKeyAPI()).read_async(
        target,
        results.append,
    )
    scheduler.drain()

    assert results == [""]
    assert clipboard.events == []


def test_missing_target_short_circuits():
    scheduler = QueuedScheduler()
    clipboard = FakeClipboard()
    results = []

    _reader(scheduler, clipboard, FakeQuartzKeyAPI()).read_async(None, results.append)

    assert results == [""]
    assert clipboard.events == []
    assert scheduler.callbacks == []


def test_unavailable_target_short_circuits():
    scheduler = QueuedScheduler()
    clipboard = FakeClipboard()
    target = FakeTarget(available=False)
    results = []

    _reader(scheduler, clipboard, FakeQuartzKeyAPI()).read_async(
        target,
        results.append,
    )

    assert results == [""]
    assert clipboard.events == []


class FakeAccessibility:
    def __init__(self, text=None):
        self.text = text
        self.calls = 0

    def selected_text(self):
        self.calls += 1
        return self.text


def test_accessibility_answer_skips_the_clipboard_entirely():
    """No synthetic Command+C, no sentinel, no clipboard to restore."""
    scheduler = QueuedScheduler()
    clipboard = FakeClipboard()
    api = FakeQuartzKeyAPI()
    target = FakeTarget(active=True)
    results = []

    SelectionReader(
        keys=KeyEventPoster(api=api),
        scheduler=scheduler,
        clipboard=clipboard,
        accessibility=FakeAccessibility("texte AX"),
    ).read_async(target, results.append)

    assert results == ["texte AX"]
    assert clipboard.events == []
    assert api.posted == []
    assert target.activation_requests == []
    assert scheduler.callbacks == []


def test_a_silent_accessibility_api_falls_back_to_the_clipboard():
    scheduler = QueuedScheduler()
    clipboard = FakeClipboard(text_after_copy="texte presse-papiers")
    accessibility = FakeAccessibility(None)
    target = FakeTarget(active=True)
    results = []

    SelectionReader(
        keys=KeyEventPoster(api=FakeQuartzKeyAPI()),
        scheduler=scheduler,
        clipboard=clipboard,
        accessibility=accessibility,
    ).read_async(target, results.append)
    scheduler.drain()

    assert accessibility.calls == 1
    assert results == ["texte presse-papiers"]

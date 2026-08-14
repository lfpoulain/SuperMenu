from src.utils import text_inserter as text_inserter_module
from src.utils.key_events import KEY_CODE_V, KeyEventPoster
from src.utils.text_inserter import TextInserter

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


class FakeTarget:
    def __init__(self):
        self.active = False
        self.activation_requests = []

    def request_activation(self, force=False):
        self.activation_requests.append(force)
        return True

    def is_current(self):
        return self.active


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


def _inserter(scheduler, api):
    return TextInserter(keys=KeyEventPoster(api=api), scheduler=scheduler)


def test_async_insertion_waits_for_main_loop_before_verifying_target(monkeypatch):
    clipboard_events = _stub_clipboard(monkeypatch)
    scheduler = QueuedScheduler()
    api = FakeQuartzKeyAPI()
    target = FakeTarget()
    results = []
    inserter = _inserter(scheduler, api)

    inserter.insert_text_async("réponse", target, lambda *args: results.append(args))

    assert results == []
    assert target.activation_requests == [False]
    target.active = True
    scheduler.drain()

    assert results == [(True, "")]
    assert clipboard_events == [
        ("set", "réponse"),
        ("restore", "snapshot", "réponse"),
    ]
    assert api.posted == [
        (KEY_CODE_V, True, api.command_flag),
        (KEY_CODE_V, False, api.command_flag),
    ]


def test_async_insertion_retries_activation_before_reporting_failure(monkeypatch):
    _stub_clipboard(monkeypatch)
    scheduler = QueuedScheduler()
    target = FakeTarget()
    results = []
    inserter = _inserter(scheduler, FakeQuartzKeyAPI())

    inserter.insert_text_async("réponse", target, lambda *args: results.append(args))
    scheduler.run_next()

    assert target.activation_requests == [False, True]
    target.active = True
    scheduler.drain()

    assert results == [(True, "")]


def test_async_insertion_still_blocks_a_real_target_change(monkeypatch):
    clipboard_events = _stub_clipboard(monkeypatch)
    scheduler = QueuedScheduler()
    target = FakeTarget()
    target.active = True
    results = []
    inserter = _inserter(scheduler, FakeQuartzKeyAPI())

    inserter.insert_text_async("réponse", target, lambda *args: results.append(args))
    scheduler.run_next()
    target.active = False
    scheduler.drain()

    assert results == [(False, "target_changed")]
    assert clipboard_events == [
        ("set", "réponse"),
        ("restore", "snapshot", "réponse"),
    ]


def test_paste_waits_for_the_user_to_let_go_of_the_shortcut(monkeypatch):
    """The window server merges held modifiers into synthetic events.

    The global shortcut fires on key down, so Command and Shift are usually
    still held when the paste is posted.
    """
    _stub_clipboard(monkeypatch)
    scheduler = QueuedScheduler()
    api = FakeQuartzKeyAPI()
    api.held = api.shift_flag | api.command_flag
    target = FakeTarget()
    target.active = True
    results = []
    inserter = _inserter(scheduler, api)

    inserter.insert_text_async("réponse", target, lambda *args: results.append(args))
    scheduler.run_next()
    scheduler.run_next()

    assert api.posted == []

    api.held = 0
    scheduler.drain()

    assert api.posted == [
        (KEY_CODE_V, True, api.command_flag),
        (KEY_CODE_V, False, api.command_flag),
    ]
    assert results == [(True, "")]


def test_paste_failure_is_reported_without_leaving_the_clipboard_dirty(monkeypatch):
    clipboard_events = _stub_clipboard(monkeypatch)
    scheduler = QueuedScheduler()
    api = FakeQuartzKeyAPI()
    api.fail_post = True
    target = FakeTarget()
    target.active = True
    results = []
    inserter = _inserter(scheduler, api)

    inserter.insert_text_async("réponse", target, lambda *args: results.append(args))
    scheduler.drain()

    assert results == [(False, "paste_failed")]
    assert ("restore", "snapshot", "réponse") in clipboard_events

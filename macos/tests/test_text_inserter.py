from src.utils import text_inserter as text_inserter_module
from src.utils.text_inserter import TextInserter


class QueuedScheduler:
    def __init__(self):
        self.callbacks = []

    def __call__(self, _delay, callback):
        self.callbacks.append(callback)

    def run_next(self):
        self.callbacks.pop(0)()


class FakeKeyboard:
    def __init__(self):
        self.events = []

    def press(self, key):
        self.events.append(("press", key))

    def release(self, key):
        self.events.append(("release", key))


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


def test_async_insertion_waits_for_main_loop_before_verifying_target(monkeypatch):
    clipboard_events = _stub_clipboard(monkeypatch)
    scheduler = QueuedScheduler()
    keyboard = FakeKeyboard()
    target = FakeTarget()
    results = []
    inserter = TextInserter(keyboard=keyboard, scheduler=scheduler)

    inserter.insert_text_async("réponse", target, lambda *args: results.append(args))

    assert results == []
    assert target.activation_requests == [False]
    target.active = True
    scheduler.run_next()
    scheduler.run_next()
    scheduler.run_next()

    assert results == [(True, "")]
    assert clipboard_events == [
        ("set", "réponse"),
        ("restore", "snapshot", "réponse"),
    ]
    assert len(keyboard.events) == 4


def test_async_insertion_retries_activation_before_reporting_failure(monkeypatch):
    _stub_clipboard(monkeypatch)
    scheduler = QueuedScheduler()
    target = FakeTarget()
    results = []
    inserter = TextInserter(keyboard=FakeKeyboard(), scheduler=scheduler)

    inserter.insert_text_async("réponse", target, lambda *args: results.append(args))
    scheduler.run_next()

    assert target.activation_requests == [False, True]
    target.active = True
    scheduler.run_next()
    scheduler.run_next()
    scheduler.run_next()

    assert results == [(True, "")]


def test_async_insertion_still_blocks_a_real_target_change(monkeypatch):
    clipboard_events = _stub_clipboard(monkeypatch)
    scheduler = QueuedScheduler()
    target = FakeTarget()
    target.active = True
    results = []
    inserter = TextInserter(keyboard=FakeKeyboard(), scheduler=scheduler)

    inserter.insert_text_async("réponse", target, lambda *args: results.append(args))
    scheduler.run_next()
    target.active = False
    scheduler.run_next()

    assert results == [(False, "target_changed")]
    assert clipboard_events == [
        ("set", "réponse"),
        ("restore", "snapshot", "réponse"),
    ]

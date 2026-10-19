"""Single instance: a second launch shows the running instance instead."""

import sys
import threading
import uuid

import pytest
from PySide6.QtWidgets import QApplication

from src import main

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("win"), reason="verrou d'instance Windows"
)


@pytest.fixture
def names(monkeypatch):
    """Noms uniques : une vraie instance de SuperMenu peut tourner à côté."""
    QApplication.instance() or QApplication([])
    suffix = uuid.uuid4().hex
    monkeypatch.setattr(main, "_INSTANCE_MUTEX_NAME", f"Local\\SuperMenuTest-{suffix}")
    monkeypatch.setattr(main, "_instance_server_name", lambda: f"SuperMenuTest-{suffix}")
    monkeypatch.setattr(main, "_INSTANCE_WAIT_MS", 150)
    return suffix


def _new_app():
    app = main.SuperMenu.__new__(main.SuperMenu)
    app._instance_server = None
    app._instance_mutex = None
    app._instance_mutex_owned = False
    app.main_window = None
    return app


class _OtherProcess:
    """Tient le verrou depuis un autre thread, comme une seconde instance."""

    def __init__(self):
        self.acquired = threading.Event()
        self.release = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.result = None

    def _run(self):
        handle, existed = main._create_instance_mutex()
        self.result = existed
        self.acquired.set()
        self.release.wait(10)
        main._close_instance_mutex(handle, owned=not existed)

    def __enter__(self):
        self.thread.start()
        assert self.acquired.wait(5)
        return self

    def __exit__(self, *exc):
        self.release.set()
        self.thread.join(5)


def _close(app):
    if app._instance_server is not None:
        app._instance_server.close()
    app._release_instance_lock()


def test_second_launch_is_refused_even_before_the_first_listens(names):
    # Deux lancements simultanés : la première instance détient le verrou
    # mais n'écoute pas encore. Avant, la seconde démarrait aussi.
    with _OtherProcess() as first:
        assert first.result is False
        second = _new_app()
        assert second._ensure_single_instance() is False
        assert second._instance_mutex is None and second._instance_server is None


def test_second_launch_asks_the_running_instance_to_show_itself(names):
    first = _new_app()
    assert first._ensure_single_instance() is True
    try:
        assert first._instance_mutex_owned and first._instance_server.isListening()
        second_result = []
        thread = threading.Thread(
            target=lambda: second_result.append(_new_app()._ensure_single_instance())
        )
        thread.start()
        thread.join(5)
        assert second_result == [False]
    finally:
        _close(first)


def test_restarted_instance_waits_for_the_previous_one_to_release_the_lock(names, monkeypatch):
    monkeypatch.setattr(main, "_INSTANCE_WAIT_MS", 5000)
    with _OtherProcess() as previous:
        threading.Timer(0.2, previous.release.set).start()
        restarted = _new_app()
        try:
            assert restarted._ensure_single_instance() is True
            assert restarted._instance_mutex_owned
        finally:
            _close(restarted)


def test_unavailable_lock_falls_back_to_the_local_channel(names, monkeypatch):
    monkeypatch.setattr(main, "_create_instance_mutex", lambda: (None, False))
    app = _new_app()
    try:
        assert app._ensure_single_instance() is True
        assert app._instance_server.isListening()
    finally:
        _close(app)


def test_close_services_releases_the_lock_for_a_restart(names):
    class Closable:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    app = _new_app()
    assert app._ensure_single_instance() is True
    app._services_closed = False
    managers = [Closable() for _ in range(7)]
    (
        app.hotkey_manager,
        app.voice_hotkey_manager,
        app.screenshot_hotkey_manager,
        app.custom_hotkey_manager,
        app.prompt_hotkey_manager,
        app.dictation_hotkey_manager,
        app.context_menu_manager,
    ) = managers
    app._close_services()

    assert all(manager.closed for manager in managers)
    assert app._instance_mutex is None and not app._instance_server.isListening()
    with _OtherProcess() as next_instance:
        assert next_instance.result is False


def test_instance_channel_is_scoped_to_the_windows_session():
    name = main._instance_server_name()
    assert name.startswith("SuperMenuSingleInstance-")
    assert name.rsplit("-", 1)[1].isdigit()

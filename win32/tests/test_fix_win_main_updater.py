"""Updater flow of the Windows main window: integrity, privileges, versions."""

import hashlib
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication, QMessageBox

from src.ui import main_window
from src.ui.main_window import MainWindow
from src.utils import updater as app_updater


def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def private_temp(monkeypatch, tmp_path):
    # Update folders are created and removed in the temp directory: keep the
    # tests away from the real %TEMP%.
    folder = tmp_path / "temp"
    folder.mkdir()
    monkeypatch.setattr(main_window.tempfile, "tempdir", str(folder))
    return folder


class _UpdateOwner:
    """Just what the update slots read on the window."""

    def __init__(self, silent=False):
        self._update_loading = None
        self._update_check_silent = silent
        self._update_expected_sha256 = None
        self.downloads = []
        self.releases_opened = 0

    def _start_download_installer(self, url, file_name, expected_sha256=None):
        self.downloads.append((url, file_name, expected_sha256))

    def open_releases_page(self):
        self.releases_opened += 1


def _check_data(**overrides):
    data = {
        "channel": "stable",
        "installed_version": None,
        "latest_version": "2.1.0",
        "asset_name": "SuperMenu_Setup.exe",
        "asset_url": "https://github.com/o/r/releases/download/v2.1.0/SuperMenu_Setup.exe",
        "asset_sha256": "a" * 64,
    }
    data.update(overrides)
    return data


@pytest.fixture
def dialogs(monkeypatch):
    calls = {"question": [], "information": [], "warning": []}

    def question(*args, **_kwargs):
        calls["question"].append(args)
        return QMessageBox.Yes

    monkeypatch.setattr(main_window.QMessageBox, "question", question)
    monkeypatch.setattr(
        main_window.QMessageBox,
        "information",
        lambda *args, **_kwargs: calls["information"].append(args),
    )
    monkeypatch.setattr(
        main_window.QMessageBox,
        "warning",
        lambda *args, **_kwargs: calls["warning"].append(args),
    )
    return calls


def test_check_worker_passes_the_published_fingerprint(monkeypatch):
    release = {
        "body": "Version: 2.1.0",
        "html_url": "https://github.com/o/r/releases/tag/v2.1.0",
        "assets": [
            {
                "name": "SuperMenu_Setup.exe",
                "browser_download_url": "https://example.invalid/setup.exe",
                "digest": "sha256:" + "b" * 64,
            }
        ],
    }
    monkeypatch.setattr(app_updater, "get_release_for_update_channel", lambda *_a, **_k: release)
    monkeypatch.setattr(app_updater, "get_installed_app_version", lambda _guid: "2.0.0")
    worker = main_window._UpdateCheckWorker("o", "r", "stable", "guid")
    emitted = []
    worker.finished_ok.connect(emitted.append)

    worker.run()

    assert emitted[0]["asset_sha256"] == "b" * 64
    assert emitted[0]["asset_url"] == "https://example.invalid/setup.exe"
    # Source run: never the portable executable.
    assert emitted[0]["portable"] is False


def test_check_worker_reports_a_portable_build(monkeypatch):
    monkeypatch.setattr(
        app_updater,
        "get_release_for_update_channel",
        lambda *_a, **_k: {"body": "Version: 2.1.0", "assets": []},
    )
    monkeypatch.setattr(app_updater, "get_installed_app_version", lambda _guid: None)
    monkeypatch.setattr(main_window, "_is_portable_build", lambda guid: guid == "guid")
    worker = main_window._UpdateCheckWorker("o", "r", "stable", "guid")
    emitted = []
    worker.finished_ok.connect(emitted.append)

    worker.run()

    assert emitted[0]["portable"] is True


def test_installer_is_downloaded_by_name_with_its_fingerprint(dialogs):
    owner = _UpdateOwner()

    MainWindow._on_update_check_ok(owner, _check_data())

    # Only a file name: the private folder is chosen by the updater, never
    # the shared and predictable %TEMP% path.
    assert owner.downloads == [
        (
            "https://github.com/o/r/releases/download/v2.1.0/SuperMenu_Setup.exe",
            "SuperMenu_Setup_2.1.0.exe",
            "a" * 64,
        )
    ]


def test_download_worker_uses_the_verified_private_download(monkeypatch):
    calls = []

    def fake_download(url, file_name, expected_sha256):
        calls.append((url, file_name, expected_sha256))
        return os.path.join("private", file_name)

    monkeypatch.setattr(app_updater, "download_verified_installer", fake_download)
    worker = main_window._UpdateDownloadWorker("https://x/setup.exe", "Setup_2.exe", "c" * 64)
    done, failed = [], []
    worker.finished_ok.connect(done.append)
    worker.failed.connect(failed.append)

    worker.run()

    assert calls == [("https://x/setup.exe", "Setup_2.exe", "c" * 64)]
    assert done == [os.path.join("private", "Setup_2.exe")]
    assert failed == []


def test_download_worker_reports_an_integrity_failure(monkeypatch):
    def refuse(*_args):
        raise app_updater.UpdateIntegrityError("empreinte différente")

    monkeypatch.setattr(app_updater, "download_verified_installer", refuse)
    worker = main_window._UpdateDownloadWorker("https://x/setup.exe", "Setup.exe", "c" * 64)
    done, failed = [], []
    worker.finished_ok.connect(done.append)
    worker.failed.connect(failed.append)

    worker.run()

    assert done == []
    assert failed == ["empreinte différente"]


def test_update_folder_prefix_matches_the_updater(monkeypatch, private_temp):
    def fake_download(_url, dest_path, _timeout):
        with open(dest_path, "wb") as f:
            f.write(b"installer")
        return hashlib.sha256(b"installer").hexdigest()

    monkeypatch.setattr(app_updater, "_download_and_hash", fake_download)

    path = app_updater.download_verified_installer("https://x/setup.exe", "Setup.exe", None)
    folder = os.path.dirname(path)

    assert os.path.basename(folder).startswith(main_window._UPDATE_FOLDER_PREFIX)
    main_window._remove_update_folder(path)
    assert not os.path.exists(folder)


def test_only_private_update_folders_are_removed(tmp_path, private_temp):
    other = tmp_path / "Downloads"
    other.mkdir()
    installer = other / "SuperMenu_Setup.exe"
    installer.write_bytes(b"installer")
    # Right prefix, but not a folder of the temp directory.
    lookalike = tmp_path / "SuperMenu_update_elsewhere"
    lookalike.mkdir()
    (lookalike / "SuperMenu_Setup.exe").write_bytes(b"installer")

    main_window._remove_update_folder(str(installer))
    main_window._remove_update_folder(str(lookalike / "SuperMenu_Setup.exe"))
    main_window._remove_update_folder("")
    main_window._remove_update_folder(None)

    assert installer.is_file()
    assert (lookalike / "SuperMenu_Setup.exe").is_file()


def test_start_download_remembers_the_fingerprint_for_the_launch(monkeypatch):
    created = []

    class FakeWorker:
        def __init__(self, url, file_name, expected_sha256=None):
            created.append((url, file_name, expected_sha256))
            self.finished_ok = Mock()
            self.failed = Mock()

        def isRunning(self):
            return False

        def start(self):
            pass

    monkeypatch.setattr(main_window, "_UpdateDownloadWorker", FakeWorker)
    monkeypatch.setattr(main_window, "SimpleLoadingIndicator", Mock())
    owner = SimpleNamespace(
        _update_download_worker=None,
        _update_expected_sha256=None,
        _update_loading=None,
        _on_download_ok=Mock(),
        _on_download_failed=Mock(),
    )

    MainWindow._start_download_installer(owner, "https://x/setup.exe", "Setup.exe", "d" * 64)

    assert created == [("https://x/setup.exe", "Setup.exe", "d" * 64)]
    assert owner._update_expected_sha256 == "d" * 64


def _launch_owner(expected_sha256):
    return SimpleNamespace(_update_expected_sha256=expected_sha256)


def _fake_shell(monkeypatch, return_code, elevated=None):
    calls = []

    def shell_execute(hwnd, verb, path, params, cwd, show):
        calls.append((verb, path))
        return return_code

    shell32 = SimpleNamespace(ShellExecuteW=shell_execute)
    if elevated is not None:
        shell32.IsUserAnAdmin = lambda: int(elevated)
    fake_ctypes = SimpleNamespace(windll=SimpleNamespace(shell32=shell32))
    monkeypatch.setattr(main_window, "ctypes", fake_ctypes)
    return calls


def _installer(tmp_path, payload=b"installer"):
    path = tmp_path / "SuperMenu_Setup_2.1.0.exe"
    path.write_bytes(payload)
    return str(path), hashlib.sha256(payload).hexdigest()


def _private_installer(_tmp_path, payload=b"installer"):
    # Like download_verified_installer: a prefixed folder of the temp directory.
    folder = main_window.tempfile.mkdtemp(prefix=main_window._UPDATE_FOLDER_PREFIX)
    return _installer(Path(folder), payload)


def test_installer_replaced_before_launch_is_refused(monkeypatch, tmp_path, dialogs):
    path, digest = _installer(tmp_path)
    shell = _fake_shell(monkeypatch, 42)
    app = Mock()
    monkeypatch.setattr(main_window, "QApplication", app)
    # Replaced while the "Lancer l'installation maintenant ?" box was open.
    (tmp_path / "SuperMenu_Setup_2.1.0.exe").write_bytes(b"malicious")

    MainWindow._launch_installer_and_quit(_launch_owner(digest), path)

    assert shell == []
    app.quit.assert_not_called()
    assert "empreinte" in dialogs["warning"][0][2]


def test_installer_is_opened_without_runas_and_the_app_quits(monkeypatch, tmp_path, dialogs):
    path, digest = _installer(tmp_path)
    shell = _fake_shell(monkeypatch, 42)
    popen = Mock()
    monkeypatch.setattr(main_window.subprocess, "Popen", popen)
    app = Mock()
    monkeypatch.setattr(main_window, "QApplication", app)

    MainWindow._launch_installer_and_quit(_launch_owner(digest), path)

    # "open" lets the Inno loader elevate itself, so the post-install launch
    # of SuperMenu keeps the user's own rights.
    assert shell == [("open", path)]
    popen.assert_not_called()
    app.quit.assert_called_once()
    assert dialogs["warning"] == []


def test_refused_launch_does_not_retry_nor_quit(monkeypatch, tmp_path, dialogs):
    path, digest = _installer(tmp_path)
    shell = _fake_shell(monkeypatch, main_window._SE_ERR_ACCESSDENIED)
    popen = Mock()
    monkeypatch.setattr(main_window.subprocess, "Popen", popen)
    app = Mock()
    monkeypatch.setattr(main_window, "QApplication", app)

    MainWindow._launch_installer_and_quit(_launch_owner(digest), path)

    assert shell == [("open", path)]
    popen.assert_not_called()
    app.quit.assert_not_called()
    assert "SuperMenu reste ouvert" in dialogs["warning"][0][2]


def test_other_shell_failures_keep_the_direct_launch_fallback(monkeypatch, tmp_path, dialogs):
    path, _digest = _installer(tmp_path)
    _fake_shell(monkeypatch, 2)
    popen = Mock()
    monkeypatch.setattr(main_window.subprocess, "Popen", popen)
    app = Mock()
    monkeypatch.setattr(main_window, "QApplication", app)

    # Older manifests publish no fingerprint: the launch is still allowed.
    MainWindow._launch_installer_and_quit(_launch_owner(None), path)

    popen.assert_called_once_with([path], cwd=str(tmp_path))
    app.quit.assert_called_once()


def test_elevated_app_starts_the_installer_through_the_user_shell(monkeypatch, tmp_path, dialogs):
    path, digest = _private_installer(tmp_path)
    shell = _fake_shell(monkeypatch, 42, elevated=True)
    popen = Mock()
    monkeypatch.setattr(main_window.subprocess, "Popen", popen)
    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    app = Mock()
    monkeypatch.setattr(main_window, "QApplication", app)

    MainWindow._launch_installer_and_quit(_launch_owner(digest), path)

    # Explorer runs with the user's standard token: the Inno loader asks for
    # elevation itself and relaunches SuperMenu without administrator rights.
    assert shell == []
    popen.assert_called_once_with(
        [os.path.join(r"C:\Windows", "explorer.exe"), path],
        cwd=os.path.dirname(path),
    )
    app.quit.assert_called_once()
    assert os.path.exists(path)


def test_elevated_app_falls_back_to_open_without_explorer(monkeypatch, tmp_path, dialogs):
    path, digest = _private_installer(tmp_path)
    shell = _fake_shell(monkeypatch, 42, elevated=True)
    popen = Mock(side_effect=OSError("explorer missing"))
    monkeypatch.setattr(main_window.subprocess, "Popen", popen)
    app = Mock()
    monkeypatch.setattr(main_window, "QApplication", app)

    MainWindow._launch_installer_and_quit(_launch_owner(digest), path)

    assert shell == [("open", path)]
    app.quit.assert_called_once()


def test_standard_app_keeps_the_open_verb(monkeypatch, tmp_path, dialogs):
    path, digest = _private_installer(tmp_path)
    shell = _fake_shell(monkeypatch, 42, elevated=False)
    popen = Mock()
    monkeypatch.setattr(main_window.subprocess, "Popen", popen)
    app = Mock()
    monkeypatch.setattr(main_window, "QApplication", app)

    MainWindow._launch_installer_and_quit(_launch_owner(digest), path)

    assert shell == [("open", path)]
    popen.assert_not_called()
    app.quit.assert_called_once()


def test_explorer_is_not_used_for_a_path_with_a_comma(monkeypatch):
    popen = Mock()
    monkeypatch.setattr(main_window.subprocess, "Popen", popen)

    assert main_window._open_through_user_shell(r"C:\a,b\Setup.exe", r"C:\a,b") is False
    popen.assert_not_called()


def test_declined_installation_removes_the_downloaded_installer(monkeypatch, tmp_path):
    path, _digest = _private_installer(tmp_path)
    monkeypatch.setattr(main_window.QMessageBox, "question", lambda *_a, **_k: QMessageBox.No)
    owner = SimpleNamespace(_update_loading=None, _launch_installer_and_quit=Mock())

    MainWindow._on_download_ok(owner, path)

    owner._launch_installer_and_quit.assert_not_called()
    assert not os.path.exists(os.path.dirname(path))


def test_replaced_installer_is_removed_with_its_folder(monkeypatch, tmp_path, dialogs):
    path, digest = _private_installer(tmp_path)
    shell = _fake_shell(monkeypatch, 42)
    monkeypatch.setattr(main_window, "QApplication", Mock())
    with open(path, "wb") as f:
        f.write(b"malicious")

    MainWindow._launch_installer_and_quit(_launch_owner(digest), path)

    assert shell == []
    assert not os.path.exists(os.path.dirname(path))


def test_refused_launch_removes_the_downloaded_installer(monkeypatch, tmp_path, dialogs):
    path, digest = _private_installer(tmp_path)
    _fake_shell(monkeypatch, main_window._SE_ERR_ACCESSDENIED)
    monkeypatch.setattr(main_window, "QApplication", Mock())

    MainWindow._launch_installer_and_quit(_launch_owner(digest), path)

    assert not os.path.exists(os.path.dirname(path))


def test_launched_installer_is_kept(monkeypatch, tmp_path, dialogs):
    path, digest = _private_installer(tmp_path)
    _fake_shell(monkeypatch, 42)
    monkeypatch.setattr(main_window, "QApplication", Mock())

    MainWindow._launch_installer_and_quit(_launch_owner(digest), path)

    # The installer runs from there; the next download purges it.
    assert os.path.exists(path)


def test_portable_build_compares_the_running_version(monkeypatch, dialogs):
    monkeypatch.setattr(main_window, "APP_VERSION", "2.1.0")
    owner = _UpdateOwner()

    # No Inno registry entry: the portable executable is not "unknown".
    MainWindow._on_update_check_ok(
        owner,
        _check_data(installed_version=None, portable=True),
    )

    assert owner.downloads == []
    assert dialogs["question"] == []
    assert "Version actuelle : 2.1.0" in dialogs["information"][0][2]


def test_running_build_wins_over_an_older_installed_copy(monkeypatch, dialogs):
    monkeypatch.setattr(main_window, "APP_VERSION", "2.1.0")
    owner = _UpdateOwner()

    MainWindow._on_update_check_ok(owner, _check_data(installed_version="1.0.0"))

    assert owner.downloads == []
    assert dialogs["question"] == []


def test_portable_build_is_not_notified_in_the_background(monkeypatch, dialogs):
    monkeypatch.setattr(main_window, "APP_VERSION", "2.0.0")
    owner = _UpdateOwner(silent=True)

    MainWindow._on_update_check_ok(
        owner,
        _check_data(installed_version=None, portable=True),
    )

    # The installer cannot update it: same as before, nothing in the background.
    assert dialogs["question"] == []
    assert owner.downloads == []


def test_portable_build_beside_a_newer_installed_copy_stays_silent(monkeypatch, dialogs):
    monkeypatch.setattr(main_window, "APP_VERSION", "2.0.0")
    owner = _UpdateOwner(silent=True)

    MainWindow._on_update_check_ok(
        owner,
        _check_data(installed_version="2.1.0", latest_version="2.1.0", portable=True),
    )

    # Installing 2.1.0 again would not update this executable, day after day.
    assert dialogs["question"] == []
    assert owner.downloads == []
    assert owner.releases_opened == 0


def test_portable_manual_check_points_to_the_downloads(monkeypatch, dialogs):
    monkeypatch.setattr(main_window, "APP_VERSION", "2.0.0")
    owner = _UpdateOwner()

    MainWindow._on_update_check_ok(
        owner,
        _check_data(installed_version="2.1.0", latest_version="2.1.0", portable=True),
    )

    assert len(dialogs["question"]) == 1
    message = dialogs["question"][0][2]
    assert "Version actuelle : 2.0.0" in message
    assert "portable" in message
    assert owner.releases_opened == 1
    assert owner.downloads == []


def test_portable_manual_check_can_be_declined(monkeypatch, dialogs):
    monkeypatch.setattr(main_window, "APP_VERSION", "2.0.0")
    monkeypatch.setattr(main_window.QMessageBox, "question", lambda *_a, **_k: QMessageBox.No)
    owner = _UpdateOwner()

    MainWindow._on_update_check_ok(owner, _check_data(portable=True))

    assert owner.releases_opened == 0
    assert owner.downloads == []


def test_installed_build_receives_the_silent_notification(monkeypatch, dialogs):
    monkeypatch.setattr(main_window, "APP_VERSION", "2.0.0")
    owner = _UpdateOwner(silent=True)

    MainWindow._on_update_check_ok(
        owner,
        _check_data(installed_version="2.0.0", portable=False),
    )

    assert len(dialogs["question"]) == 1
    assert "Version actuelle : 2.0.0" in dialogs["question"][0][2]
    assert len(owner.downloads) == 1


def test_source_run_is_never_portable(monkeypatch):
    monkeypatch.setattr(
        main_window,
        "_installed_app_locations",
        lambda _guid: pytest.fail("no registry read for a source run"),
    )

    assert main_window._is_portable_build("guid", frozen=False) is False


def test_installed_executable_is_not_portable(monkeypatch, tmp_path):
    install = tmp_path / "Program Files" / "SuperMenu"
    install.mkdir(parents=True)
    # Inno writes InstallLocation with a trailing separator.
    monkeypatch.setattr(
        main_window,
        "_installed_app_locations",
        lambda _guid: [str(install).upper() + "\\"],
    )

    assert main_window._is_portable_build(
        "guid",
        executable=str(install / "SuperMenu.exe"),
        frozen=True,
    ) is False


def test_executable_outside_the_installed_folder_is_portable(monkeypatch, tmp_path):
    install = tmp_path / "Program Files" / "SuperMenu"
    install.mkdir(parents=True)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    monkeypatch.setattr(main_window, "_installed_app_locations", lambda _guid: [str(install)])

    assert main_window._is_portable_build(
        "guid",
        executable=str(downloads / "SuperMenu.exe"),
        frozen=True,
    ) is True

    monkeypatch.setattr(main_window, "_installed_app_locations", lambda _guid: [])
    assert main_window._is_portable_build(
        "guid",
        executable=str(install / "SuperMenu.exe"),
        frozen=True,
    ) is True


def test_installed_locations_read_is_harmless_without_an_installation():
    assert main_window._installed_app_locations("00000000-0000-0000-0000-000000000000") == []


def test_source_run_keeps_the_installed_version(monkeypatch, dialogs):
    monkeypatch.setattr(main_window, "APP_VERSION", "dev")
    silent_owner = _UpdateOwner(silent=True)

    MainWindow._on_update_check_ok(silent_owner, _check_data(installed_version=None))
    assert dialogs["question"] == []

    owner = _UpdateOwner()
    MainWindow._on_update_check_ok(owner, _check_data(installed_version="2.1.0"))
    assert owner.downloads == []
    assert "Version actuelle : 2.1.0" in dialogs["information"][0][2]


def test_about_page_shows_the_running_build_first(monkeypatch):
    monkeypatch.setattr(main_window, "APP_VERSION", "2.1.0")
    monkeypatch.setattr(app_updater, "get_installed_app_version", lambda _guid: "1.0.0")
    assert MainWindow._get_installed_version_display(None) == "2.1.0"

    monkeypatch.setattr(main_window, "APP_VERSION", "dev")
    assert MainWindow._get_installed_version_display(None) == "1.0.0"
    monkeypatch.setattr(app_updater, "get_installed_app_version", lambda _guid: None)
    assert MainWindow._get_installed_version_display(None) == "dev"


@pytest.mark.parametrize(
    "worker_class",
    ["_UpdateCheckWorker", "_UpdateDownloadWorker", "_CustomModelsWorker"],
)
def test_workers_are_not_qthreads(worker_class):
    # A QThread destroyed while running aborts the whole process.
    assert not issubclass(getattr(main_window, worker_class), QThread)


def test_worker_runs_on_a_daemon_thread_and_reports_on_the_qt_thread(monkeypatch):
    app = _app()
    monkeypatch.setattr(
        app_updater,
        "download_verified_installer",
        lambda _url, file_name, _sha: file_name,
    )
    worker = main_window._UpdateDownloadWorker("https://x/setup.exe", "Setup.exe")
    received, finished = [], []
    worker.finished_ok.connect(lambda path: received.append((path, QThread.currentThread())))
    worker.finished.connect(lambda: finished.append(True))

    worker.start()
    assert worker._thread.daemon is True
    worker._thread.join(5)
    for _ in range(20):
        app.processEvents()
        if received and finished:
            break

    assert worker.isRunning() is False
    assert received == [("Setup.exe", app.thread())]
    assert finished == [True]


def test_quitting_during_a_request_exits_cleanly(tmp_path):
    win32_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    shared_dir = os.path.join(os.path.dirname(win32_dir), "shared")
    script = tmp_path / "quit_during_request.py"
    script.write_text(
        textwrap.dedent(
            """
            import threading
            from PySide6.QtCore import QTimer
            from PySide6.QtWidgets import QApplication

            from src.ui import main_window
            from src.utils import updater as app_updater

            blocked = threading.Event()
            app_updater.get_release_for_update_channel = (
                lambda *_args, **_kwargs: blocked.wait(60)
            )
            app = QApplication([])
            worker = main_window._UpdateCheckWorker("o", "r", "stable", "guid")
            worker.start()
            QTimer.singleShot(100, app.quit)
            app.exec()
            print("exited")
            """
        ),
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["PYTHONPATH"] = os.pathsep.join(
        [win32_dir, shared_dir, environment.get("PYTHONPATH", "")]
    )

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=win32_dir,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "exited" in result.stdout
    assert "Destroyed while thread" not in result.stderr

import gc
import os
import tempfile
from pathlib import Path

# The tests log errors on purpose (failed workers, missing DLLs...): write them
# to a temporary folder, never to win32/logs, the journal of the application
# run from the sources. Set before src.utils.logger is first imported.
os.environ.setdefault(
    "SUPERMENU_LOG_DIR",
    str(Path(tempfile.gettempdir()) / f"supermenu-win32-tests-{os.getpid()}" / "logs"),
)

import pytest  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402

from supermenu_core.config import feature_modes  # noqa: E402


@pytest.fixture(autouse=True)
def _feature_modes_of_updated_installs(monkeypatch):
    """Earlier tests build fresh settings files and exercise every feature.

    An update keeps both feature switches on, so these tests run as an updated
    installation. Tests of a new installation set NEW_INSTALL_ENABLED to False.
    """
    monkeypatch.setattr(feature_modes, "NEW_INSTALL_ENABLED", True)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """Destroy the Qt objects a test leaves behind before the next one starts.

    Tests leave context menu managers and their response windows in reference
    cycles (undoing ``monkeypatch.setattr(manager, ...)`` stores the bound
    method back on the instance), so only the cyclic garbage collector frees
    them. Python 3.11 runs it on any allocation, including those PySide makes
    while Qt hands an event to the application event filter of a later
    ContextMenuManager and creates the Python event types on first use. A
    QWidget destroyed there sends its own events through that filter while
    those types are half created, and the process crashes (access violation).
    Python 3.12 only collects between bytecodes, where it never happened.

    Collected here, once the fixtures and the test arguments are released, they
    are destroyed while no Qt call is running.

    The windows a test scheduled with ``deleteLater()`` are destroyed here too:
    no event loop runs between tests, so Qt would keep them alive and every
    later ``QApplication.setStyleSheet`` would restyle all of them.
    """
    try:
        return (yield)
    finally:
        gc.collect()
        if QCoreApplication.instance() is not None:
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

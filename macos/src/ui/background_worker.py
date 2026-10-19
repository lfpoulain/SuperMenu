"""Background requests of the configuration window without a QThread."""

from __future__ import annotations

import threading
from PySide6.QtCore import QObject, Signal


class _BackgroundWorker(QObject):
    """Run one blocking request on a daemon thread and report through signals.

    A ``QThread`` still running when Python destroys it aborts the whole
    process ("QThread: Destroyed while thread is still running"): quitting
    during the startup update check or a model refresh was enough to produce a
    macOS crash report. A daemon thread is simply abandoned at exit instead,
    as ``CatalogWorker`` already does. The QThread-like ``start``,
    ``isRunning`` and ``finished`` surface is kept for the callers.
    """

    finished = Signal()

    def __init__(self):
        super().__init__()
        self._thread = None

    def isRunning(self):
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            self.run()
        finally:
            try:
                self.finished.emit()
            except RuntimeError:
                # The window owning this worker was destroyed during exit.
                pass

    def run(self):
        raise NotImplementedError

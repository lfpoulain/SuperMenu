"""Explicit packaged microphone check; samples are counted and discarded."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from .microphone import Microphone


def run_microphone_check(report, rate=16000):
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    microphone = Microphone(rate)
    state = {"microphone_ok": False, "pcm_bytes": 0, "sample_rate": rate}

    def received(pcm):
        state["pcm_bytes"] += len(pcm)

    def finish(error=None):
        if state.get("finished"):
            return
        state["finished"] = True
        microphone.stop()
        state["microphone_ok"] = state["pcm_bytes"] > 0 and not error
        if error:
            state["error"] = error
        report({k: v for k, v in state.items() if k != "finished"})
        app.exit(0 if state["microphone_ok"] else 1)

    def start():
        try:
            microphone.start()
            QTimer.singleShot(400, microphone, lambda: finish())
        except Exception as exc:
            finish(str(exc))

    microphone.chunk.connect(received)
    microphone.failed.connect(finish)
    QTimer.singleShot(0, microphone, start)
    return app.exec()

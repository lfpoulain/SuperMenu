"""Press/release semantics shared by native shortcut registrations."""

from PySide6.QtCore import QObject, Signal


class ReleaseBinding:
    """Callable accepted by ordinary bindings, with an optional release edge."""

    def __init__(self, pressed, released):
        self.pressed = pressed
        self.release = released

    def __call__(self):
        self.pressed()


class DictationShortcut(QObject):
    started = Signal()
    released = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._pressed = False
        self._hold = False

    def press(self):
        if self._pressed:
            return
        self._pressed = True
        self._hold = self.settings.get_dictation_hotkey_mode() == "hold"
        self.started.emit()

    def release(self):
        if not self._pressed:
            return
        self._pressed = False
        if self._hold:
            self.released.emit()

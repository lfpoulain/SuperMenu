from PySide6.QtCore import QObject, Signal, QBuffer, QIODevice
from PySide6.QtMultimedia import QAudioFormat, QtAudio
from PySide6.QtWidgets import QApplication

from supermenu_core.audio import microphone as audio


def test_qt_audio_no_error_keeps_microphone_open(monkeypatch):
    app = QApplication.instance() or QApplication([])
    fmt = QAudioFormat()
    fmt.setSampleRate(16000)
    fmt.setChannelCount(1)
    fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)

    class Device:
        def id(self):
            return b"mic"

        def isNull(self):
            return False

        def isFormatSupported(self, _fmt):
            return True

        def preferredFormat(self):
            return fmt

    class Devices:
        audioInputs = staticmethod(lambda: [Device()])
        defaultAudioInput = staticmethod(Device)

    class Source(QObject):
        stateChanged = Signal(object)

        def __init__(self, *_args):
            super().__init__()
            self.buffer = QBuffer(self)
            self.buffer.setData(b"\x00\x10" * 1600)
            self.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            self.stopped = False

        def setBufferSize(self, _size):
            pass

        def start(self):
            return self.buffer

        def error(self):
            return QtAudio.Error.NoError

        def state(self):
            return QtAudio.State.StoppedState

        def stop(self):
            self.stopped = True

    monkeypatch.setattr(audio, "QMediaDevices", Devices)
    monkeypatch.setattr(audio, "QAudioSource", Source)
    mic = audio.Microphone(16000)
    chunks, errors = [], []
    mic.chunk.connect(chunks.append)
    mic.failed.connect(errors.append)
    mic.start()
    source = mic.source
    assert not source.stopped
    mic._read()
    assert b"".join(chunks) == b"\x00\x10" * 1600
    source.stateChanged.emit(QtAudio.State.StoppedState)
    assert not errors
    source.error = lambda: QtAudio.Error.IOError
    source.stateChanged.emit(QtAudio.State.StoppedState)
    assert len(errors) == 1
    mic.stop()
    assert source.stopped
    assert app is not None

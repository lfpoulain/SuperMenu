"""Qt microphone capture: bounded PCM chunks, no audio files on disk."""

from array import array
import audioop

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSource, QMediaDevices


def microphones():
    return [(bytes(d.id()).hex(), d.description()) for d in QMediaDevices.audioInputs()]


class PCMConverter:
    def __init__(self, source_format, output_rate):
        self.format = source_format
        self.output_rate = output_rate
        self.state = None
        self.pending = b""

    def convert(self, data):
        data = self.pending + data
        frame_size = self.format.bytesPerFrame()
        usable = len(data) - len(data) % frame_size
        self.pending, data = data[usable:], data[:usable]
        if not data:
            return b""
        kind = self.format.sampleFormat()
        width = self.format.bytesPerSample()
        if kind == QAudioFormat.SampleFormat.Float:
            samples = array("f")
            samples.frombytes(data)
            data = array(
                "h", (max(-32768, min(32767, round(v * 32767))) for v in samples)
            ).tobytes()
        else:
            if kind == QAudioFormat.SampleFormat.UInt8:
                data = audioop.bias(data, 1, -128)
            data = audioop.lin2lin(data, width, 2)
        channels = self.format.channelCount()
        if channels == 2:
            data = audioop.tomono(data, 2, 0.5, 0.5)
        elif channels > 2:
            samples = array("h")
            samples.frombytes(data)
            data = array(
                "h",
                (
                    round(sum(samples[i : i + channels]) / channels)
                    for i in range(0, len(samples), channels)
                ),
            ).tobytes()
        data, self.state = audioop.ratecv(
            data, 2, 1, self.format.sampleRate(), self.output_rate, self.state
        )
        return data


class Microphone(QObject):
    chunk = Signal(bytes)
    level = Signal(int)
    failed = Signal(str)

    def __init__(self, rate, device_id="", parent=None):
        super().__init__(parent)
        self.rate, self.device_id = rate, device_id
        self.source = None
        self.stream = None
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._read)

    def start(self):
        devices = QMediaDevices.audioInputs()
        device = next(
            (d for d in devices if bytes(d.id()).hex() == self.device_id), None
        )
        if self.device_id and device is None:
            raise RuntimeError(
                "Le microphone choisi est déconnecté. Choisissez un autre microphone dans les réglages de dictée."
            )
        device = device or QMediaDevices.defaultAudioInput()
        if device.isNull():
            raise RuntimeError(
                "Aucun microphone disponible. Branchez un microphone et réessayez."
            )
        fmt = QAudioFormat()
        fmt.setSampleRate(self.rate)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if not device.isFormatSupported(fmt):
            fmt = device.preferredFormat()
        self.converter = PCMConverter(fmt, self.rate)
        self.source = QAudioSource(device, fmt, self)
        self.source.setBufferSize(fmt.bytesForDuration(250_000))
        self.stream = self.source.start()
        if self.stream is None or self.source.error() != QAudio.Error.NoError:
            self.stop()
            raise RuntimeError(
                "Impossible d’ouvrir le microphone. Vérifiez son autorisation et le périphérique choisi."
            )
        self.source.stateChanged.connect(self._state_changed)
        self.timer.start()

    def _state_changed(self, state):
        if (
            self.source
            and state == QAudio.State.StoppedState
            and self.source.error() != QAudio.Error.NoError
        ):
            self.failed.emit("Le microphone a été interrompu ou déconnecté.")

    def _read(self):
        if self.stream is None:
            return
        data = self.converter.convert(bytes(self.stream.readAll()))
        if data:
            self.level.emit(min(100, round(audioop.rms(data, 2) / 100)))
            # Bound each message, even after a delayed UI event-loop turn.
            for offset in range(0, len(data), self.rate // 5):
                if self.stream is None:
                    break
                self.chunk.emit(data[offset : offset + self.rate // 5])

    def stop(self, flush=False):
        self.timer.stop()
        if flush:
            self._read()
        source, self.source = self.source, None
        self.stream = None
        if source:
            source.stop()
            source.deleteLater()

import io
import json
from types import SimpleNamespace

from src.audio.foundry_speech_worker import run, select_speech_model


class Session:
    settings = SimpleNamespace()

    def start(self):
        pass

    def get_stream(self):
        for text, final in (
            (" Bonjour", False),
            (" monde", False),
            ("Bonjour, monde.", True),
        ):
            yield SimpleNamespace(content=[SimpleNamespace(text=text)], is_final=final)

    def append(self, pcm):
        assert pcm == b"\x00\x00"

    def stop(self):
        pass


def model(provider, cached):
    return SimpleNamespace(
        info=SimpleNamespace(
            runtime=SimpleNamespace(
                execution_provider=provider,
                device_type="CPU" if provider == "CPUExecutionProvider" else "GPU",
            ),
            file_size_mb=756,
        ),
        is_cached=cached,
        load=lambda: None,
        unload=lambda: None,
        get_audio_client=lambda: SimpleNamespace(
            create_live_transcription_session=Session
        ),
    )


def runtime():
    models = [model("CPUExecutionProvider", True), model("CUDAExecutionProvider", True)]
    return SimpleNamespace(
        prepare_hardware=lambda *_: None,
        hardware_warning=None,
        manager=SimpleNamespace(
            catalog=SimpleNamespace(
                get_model=lambda _: SimpleNamespace(variants=models)
            )
        ),
    )


def test_voice_prefers_cuda_even_when_cpu_is_cached():
    assert (
        select_speech_model(
            runtime(), "auto", lambda _: None
        ).info.runtime.execution_provider
        == "CUDAExecutionProvider"
    )
    assert (
        select_speech_model(runtime(), "cpu", lambda _: None).info.runtime.device_type
        == "CPU"
    )


def test_final_nemotron_snapshot_replaces_partial_deltas():
    messages = [{"language": "fr"}, {"audio": "AAA="}, {"action": "stop"}]
    events = []
    run(io.StringIO("\n".join(map(json.dumps, messages))), events.append, runtime())
    snapshots = [e["text"] for e in events if e["event"] == "transcript"]
    assert snapshots == ["Bonjour", "Bonjour monde", "Bonjour, monde."]
    assert events[-1] == {"event": "complete", "text": "Bonjour, monde."}


def test_probe_reports_actual_selected_device():
    events = []
    run(io.StringIO('{"action":"probe","device":"auto"}'), events.append, runtime())
    assert events[-1]["data"]["cached"] is True
    assert "CUDA" in events[-1]["data"]["device"]

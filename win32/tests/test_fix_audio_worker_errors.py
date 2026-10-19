"""SDK failures in the Nemotron worker keep the dictation's session id."""

import io
import json
from types import SimpleNamespace

import pytest

from src.audio.foundry_speech_worker import UNEXPECTED_ERROR, run


def runtime(load):
    model = SimpleNamespace(
        id="nemotron-cpu:3",
        info=SimpleNamespace(
            runtime=SimpleNamespace(
                execution_provider="CPUExecutionProvider", device_type="CPU"
            ),
            file_size_mb=756,
        ),
        is_cached=True,
        load=load,
        unload=lambda: None,
    )
    return SimpleNamespace(
        prepare_hardware=lambda *_: None,
        hardware_warning=None,
        manager=SimpleNamespace(
            catalog=SimpleNamespace(
                get_model=lambda _: SimpleNamespace(variants=[model])
            )
        ),
    )


def test_model_load_failure_is_reported_to_its_session():
    def load():
        raise RuntimeError("Mémoire GPU insuffisante")

    request = {"action": "start", "keep_alive": True, "session_id": "abc"}
    events = []
    with pytest.raises(RuntimeError):
        run(io.StringIO(json.dumps(request) + "\n"), events.append, runtime(load))
    assert events[-1] == {
        "event": "error",
        "message": UNEXPECTED_ERROR,
        "session_id": "abc",
    }


def test_probe_failure_keeps_sessionless_error():
    def prepare(*_args):
        raise RuntimeError("SDK indisponible")

    state = runtime(lambda: None)
    state.prepare_hardware = prepare
    events = []
    with pytest.raises(RuntimeError):
        run(io.StringIO('{"action":"probe","device":"auto"}\n'), events.append, state)
    assert events[-1] == {"event": "error", "message": UNEXPECTED_ERROR}

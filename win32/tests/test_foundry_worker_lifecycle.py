"""Regression tests for the Foundry worker lifecycle (timeouts, queue, restart)."""

import json
import os
import sys
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QApplication

from src.api import foundry_client
from src.api.foundry_client import FoundryClient, FoundryService
from src.api.foundry_worker import LocalError, configure_text_model


WORKER = """import json,sys,time
for line in sys.stdin:
 r=json.loads(line)
 mode=r.get('mode')
 if mode=='progress':
  for i in range(8):
   print(json.dumps({'id':r['id'],'progress':{'percent':i*10}}),flush=True)
   time.sleep(0.1)
 elif mode=='stall':
  time.sleep(20)
 elif mode=='slow':
  time.sleep(0.6)
 elif mode=='think':
  print(json.dumps({'id':r['id'],'progress':{'phase':'generate','stage':'Raisonnement'}}),flush=True)
  time.sleep(0.5)
 print(json.dumps({'id':r['id'],'loaded_model':r['operation']=='generate','result':{'text':r.get('content','ok')}}),flush=True)
"""


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def service(app, tmp_path):
    worker = tmp_path / "worker.py"
    worker.write_text(WORKER, encoding="utf-8")
    instance = FoundryService(command=(sys.executable, [str(worker)]))
    events = SimpleNamespace(errors=[], results=[], progress=[])
    instance.failed.connect(lambda *args: events.errors.append(args))
    instance.completed.connect(lambda *args: events.results.append(args))
    instance.progress.connect(lambda *args: events.progress.append(args))
    instance.events = events
    yield instance
    instance.close()


def wait_until(app, predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert predicate()


def fast_budgets(app, service, monkeypatch, **values):
    # Start the worker first so tiny budgets never include interpreter startup.
    service.submit("generate", request_id="warm-up")
    wait_until(app, lambda: service.events.results)
    service.events.results.clear()
    service.events.progress.clear()
    budgets = dict(foundry_client.OPERATION_TIMEOUTS_MS)
    budgets.update(values)
    monkeypatch.setattr(foundry_client, "OPERATION_TIMEOUTS_MS", budgets)


def test_progressing_download_is_never_killed_by_its_silence_budget(
    app, service, monkeypatch
):
    # 8 progress messages over ~0.8 s, each well within a 300 ms budget.
    fast_budgets(app, service, monkeypatch, download=300)
    service.submit("download", request_id="dl", mode="progress", content="done")
    wait_until(app, lambda: service.events.results or service.events.errors)
    assert service.events.errors == []
    assert service.events.results == [("dl", {"text": "done"})]


@pytest.mark.parametrize(
    "operation,payload,expected",
    [
        ("download", {}, "Le téléchargement du modèle ne progresse plus"),
        ("probe", {}, "La vérification de Foundry Local"),
        ("generate", {}, "Essayez le modèle 4B ou un texte plus court"),
        ("generate", {"reasoning_mode": "on"}, "Essayez sans raisonnement"),
        ("unload", {}, "Le moteur local n'a pas répondu à temps"),
    ],
)
def test_timeout_message_matches_the_operation(
    app, service, monkeypatch, operation, payload, expected
):
    fast_budgets(app, service, monkeypatch, **{operation: 150})
    monkeypatch.setattr(foundry_client, "DEFAULT_TIMEOUT_MS", 150)
    service.submit(operation, request_id="stuck", mode="stall", **payload)
    wait_until(app, lambda: service.events.errors)
    assert service.events.errors[0][0] == "stuck"
    assert expected in service.events.errors[0][1]
    if operation == "download":
        assert "texte plus court" not in service.events.errors[0][1]


@pytest.mark.parametrize("reasoning_mode,succeeds", [("on", True), ("off", False)])
def test_reasoning_generation_gets_a_longer_budget(
    app, service, monkeypatch, reasoning_mode, succeeds
):
    fast_budgets(app, service, monkeypatch, generate=200)
    monkeypatch.setattr(foundry_client, "REASONING_GENERATION_TIMEOUT_MS", 3000)
    service.submit(
        "generate", request_id="g", mode="think", reasoning_mode=reasoning_mode
    )
    wait_until(app, lambda: service.events.results or service.events.errors)
    assert bool(service.events.results) is succeeds


def test_reasoning_budget_scales_with_output_tokens():
    budget = FoundryService._timeout_ms
    reasoning = {"operation": "generate", "reasoning_mode": "on"}
    assert budget(reasoning) == foundry_client.OPERATION_TIMEOUTS_MS["generate"]
    assert budget(reasoning, {"phase": "load"}) == foundry_client.OPERATION_TIMEOUTS_MS["generate"]
    assert budget(reasoning, {"phase": "generate"}) == 4 * 600000
    assert budget({"operation": "generate", "reasoning_mode": "off"}, {"phase": "generate"}) == 600000
    assert budget({"operation": "download"}, {"percent": 3}) == 1800000
    assert budget({"operation": "unload"}) == foundry_client.DEFAULT_TIMEOUT_MS


@pytest.mark.parametrize("download_running", [False, True])
def test_text_action_waiting_behind_a_download_is_told_why(
    app, service, monkeypatch, download_running
):
    monkeypatch.setattr(foundry_client, "platform_error", lambda: "")
    settings = SimpleNamespace(
        get_foundry_model=lambda: "qwen3.5-4b",
        get_foundry_device=lambda: "auto",
        get_text_idle_seconds=lambda: 300,
    )
    client = FoundryClient(settings, service)
    stages, finished = [], []
    client.request_progress_scoped.connect(lambda *args: stages.append(args))
    client.request_finished_scoped.connect(lambda *args: finished.append(args))
    service.submit("download", request_id="dl", mode="slow")
    if download_running:
        # The usual case: the text action starts while a download already runs.
        wait_until(
            app,
            lambda: service._active is not None
            and service._active["id"] == "dl"
            and service._process is not None
            and service._process.state() == QProcess.Running,
        )
    client.send_request("Corrige", "texte", request_id="text")
    wait_until(app, lambda: finished)
    waiting = [d for rid, d in stages if rid == "text" and d.get("phase") == "queue"]
    assert waiting and waiting[0]["stage"] == foundry_client.WAIT_MESSAGES["download"]
    assert finished[0][:2] == ("text", "texte")
    client.close()


def test_generation_queued_behind_generation_gets_no_wait_notice(app, service):
    service.submit("generate", request_id="a", mode="slow")
    service.submit("generate", request_id="b")
    wait_until(app, lambda: len(service.events.results) == 2)
    assert not [p for p in service.events.progress if p[1].get("phase") == "queue"]


def record_notices(service):
    # The fake worker sends no progress in these modes: every stage is a notice.
    notices = []
    service.progress.connect(
        lambda request_id, details: notices.append(
            (service._active and service._active["id"], request_id, details.get("stage"))
        )
    )
    return notices


def test_wait_notice_is_replaced_once_the_download_is_over(app, service):
    notices = record_notices(service)
    service.submit("download", request_id="dl", mode="slow")
    service.submit("generate", request_id="g1", mode="slow")
    service.submit("generate", request_id="g2")
    wait_until(app, lambda: len(service.events.results) == 3)
    download = foundry_client.WAIT_MESSAGES["download"]

    def seen(request_id):
        return [(active, stage) for active, rid, stage in notices if rid == request_id]

    # g2 must not keep the download notice during the whole generation of g1.
    assert seen("g2") == [
        ("dl", download),
        ("g1", foundry_client.QUEUE_MESSAGE),
        ("g2", foundry_client.START_MESSAGE),
    ]
    assert seen("g1") == [("dl", download), ("g1", foundry_client.START_MESSAGE)]


def test_wait_notice_is_replaced_when_the_download_is_cancelled(app, service):
    notices = record_notices(service)
    service.submit("download", request_id="dl", mode="stall")
    service.submit("generate", request_id="g1", content="un")
    wait_until(
        app,
        lambda: service._active is not None
        and service._process is not None
        and service._process.state() == QProcess.Running,
    )
    old = service._process
    slow_kill(old, 2000)
    service.cancel("dl")
    queued = (None, "g1", foundry_client.QUEUE_MESSAGE)
    wait_until(app, lambda: notices[-1] == queued)
    assert service._retiring is old  # Still waiting for the killed worker.
    wait_until(app, lambda: service.events.results)
    assert service.events.results == [("g1", {"text": "un"})]
    assert [stage for _active, rid, stage in notices if rid == "g1"] == [
        foundry_client.WAIT_MESSAGES["download"],
        foundry_client.QUEUE_MESSAGE,
        foundry_client.START_MESSAGE,
    ]


def slow_kill(process, delay_ms):
    real_kill = process.kill
    # Simulate a worker whose native teardown (CUDA memory) outlasts the wait.
    process.kill = lambda: QTimer.singleShot(delay_ms, real_kill) if delay_ms else None
    return real_kill


def test_slow_worker_exit_does_not_fail_the_next_request(app, service):
    service.submit("generate", request_id="slow", mode="stall")
    wait_until(
        app,
        lambda: service._active is not None
        and service._process is not None
        and service._process.state() == QProcess.Running,
    )
    old = service._process
    slow_kill(old, 1500)
    service.submit("generate", request_id="next", content="ok")
    service.cancel("slow")
    assert service._retiring is old  # The next request waits for the real exit.
    wait_until(app, lambda: service.events.results)
    assert service.events.errors == [("slow", "Opération locale annulée.")]
    assert service.events.results == [("next", {"text": "ok"})]
    assert service._process is not old and service._retiring is None


def test_unkillable_worker_does_not_block_the_queue_forever(app, service, monkeypatch):
    monkeypatch.setattr(foundry_client, "RETIRE_GRACE_MS", 200)
    service.submit("generate", request_id="stuck", mode="stall")
    wait_until(
        app,
        lambda: service._process is not None
        and service._process.state() == QProcess.Running,
    )
    old = service._process
    real_kill = slow_kill(old, 0)
    service.submit("generate", request_id="next", content="ok")
    service.cancel("stuck")
    try:
        wait_until(app, lambda: service.events.results)
        assert service.events.results == [("next", {"text": "ok"})]
        assert service._process is not old
    finally:
        real_kill()
        old.waitForFinished(3000)
    # The late exit of the replaced worker, once the queue is idle, is harmless
    # (a late exit during the next request is covered below).
    for _ in range(20):
        app.processEvents()
    assert service.events.errors == [("stuck", "Opération locale annulée.")]
    service.submit("generate", request_id="after", content="encore")
    wait_until(app, lambda: len(service.events.results) == 2)
    assert service.events.results[-1] == ("after", {"text": "encore"})


def test_late_exit_of_a_replaced_worker_does_not_fail_the_next_request(
    app, service, monkeypatch
):
    # After RETIRE_GRACE_MS two workers coexist: only the current one counts.
    monkeypatch.setattr(foundry_client, "RETIRE_GRACE_MS", 200)
    service.submit("generate", request_id="stuck", mode="stall")
    wait_until(
        app,
        lambda: service._process is not None
        and service._process.state() == QProcess.Running,
    )
    old = service._process
    real_kill = slow_kill(old, 0)
    service.submit("generate", request_id="next", mode="stall")
    service.cancel("stuck")
    try:
        wait_until(
            app,
            lambda: service._active is not None
            and service._active["id"] == "next"
            and service._process is not None
            and service._process is not old
            and service._process.state() == QProcess.Running,
        )
        current = service._process
    finally:
        real_kill()
        old.waitForFinished(3000)
    for _ in range(50):
        app.processEvents()
    # The old worker's late exit neither fails "next" nor kills its worker.
    assert service.events.errors == [("stuck", "Opération locale annulée.")]
    assert service._active is not None and service._active["id"] == "next"
    assert service._process is current
    assert current.state() == QProcess.Running
    service.cancel("next")
    assert service.events.errors[-1] == ("next", "Opération locale annulée.")


def test_unreadable_manifest_of_another_model_is_ignored(tmp_path):
    models = tmp_path / "cache/models/Microsoft"
    broken = models / "nemotron/v1"
    broken.mkdir(parents=True)
    (broken / "inference_model.json").write_text("{partial", encoding="utf-8")
    other = models / "other/v1"
    other.mkdir(parents=True)
    (other / "inference_model.json").write_text("[1, 2]", encoding="utf-8")
    invalid = models / "invalid/v1"
    invalid.mkdir(parents=True)
    (invalid / "inference_model.json").write_bytes(b"\xff\xfe\x00garbage")
    folder = models / "qwen/v3"
    folder.mkdir(parents=True)
    (folder / "inference_model.json").write_text(json.dumps({"Name": "qwen:3"}))
    (folder / "chat_template.jinja").write_text("{% if enable_thinking %}x{% endif %}")
    (folder / "genai_config.json").write_text(json.dumps({"search": {}}))
    configure_text_model(tmp_path, "qwen:3")
    assert "supermenu:reasoning:on" in (folder / "chat_template.jinja").read_text()
    with pytest.raises(LocalError, match="incomplets"):
        configure_text_model(tmp_path, "missing")

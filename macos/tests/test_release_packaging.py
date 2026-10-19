"""macOS packaging: pinned dependencies and smoke tests of the native
helpers."""

import importlib.util
import io
import json
import re
from pathlib import Path

import pytest


MACOS_ROOT = Path(__file__).resolve().parents[1]


def _load_checker():
    path = MACOS_ROOT / "scripts" / "check_native_helper.py"
    spec = importlib.util.spec_from_file_location("check_native_helper", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _requirements():
    lines = (MACOS_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith(("#", "-e", "-r"))
    ]


def test_signed_dmg_dependencies_are_pinned_exactly():
    requirements = _requirements()

    assert requirements
    for requirement in requirements:
        assert re.fullmatch(r"[A-Za-z0-9_.-]+==[0-9][0-9A-Za-z.]*", requirement), (
            requirement
        )


def test_pyobjc_packages_share_one_version_including_the_core():
    versions = {
        name: version
        for name, version in (
            requirement.split("==") for requirement in _requirements()
        )
        if name.startswith("pyobjc")
    }

    # The framework wheels only require pyobjc-core>=, so an unpinned core
    # could silently move to a newer release than the bindings.
    assert {
        "pyobjc-core",
        "pyobjc-framework-Cocoa",
        "pyobjc-framework-Quartz",
        "pyobjc-framework-CoreText",
        "pyobjc-framework-ApplicationServices",
    } <= set(versions)
    assert len(set(versions.values())) == 1


@pytest.mark.parametrize("os_major", [0, 14, 15])
def test_os_unsupported_is_accepted_on_runners_older_than_macos_26(os_major):
    checker = _load_checker()

    checker.check_reply("foundation", {"ok": False, "code": "os_unsupported"}, os_major)
    checker.check_reply(
        "speech", {"event": "error", "code": "os_unsupported"}, os_major
    )


@pytest.mark.parametrize("kind", ["foundation", "speech"])
def test_os_unsupported_fails_the_build_on_macos_26(kind):
    checker = _load_checker()
    reply = {"ok": False, "code": "os_unsupported"}
    if kind == "speech":
        reply = {"event": "error", "code": "os_unsupported"}

    with pytest.raises(AssertionError):
        checker.check_reply(kind, reply, 26)


def test_real_helper_answers_are_accepted_on_macos_26():
    checker = _load_checker()

    checker.check_reply("foundation", {"ok": True}, 26)
    for code in checker.FOUNDATION_UNAVAILABLE_CODES:
        checker.check_reply("foundation", {"ok": False, "code": code}, 26)
    checker.check_reply("speech", {"event": "result", "text": ""}, 26)


@pytest.mark.parametrize(
    ("kind", "reply"),
    [
        ("foundation", {"code": "os_unsupported"}),
        ("foundation", {"ok": "false", "code": "unavailable"}),
        ("foundation", {"ok": False, "code": "invalid_request"}),
        ("speech", {"event": "error", "code": "missing_model"}),
        ("speech", []),
        ("other", {"ok": True}),
    ],
)
def test_unexpected_helper_answers_fail(kind, reply):
    checker = _load_checker()

    with pytest.raises(AssertionError):
        checker.check_reply(kind, reply, 15)


def test_checker_entry_point_reads_stdin(monkeypatch, capsys):
    checker = _load_checker()
    monkeypatch.setattr(checker, "macos_major_version", lambda: 26)

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"ok": True})))
    assert checker.main(["check_native_helper.py", "foundation"]) == 0

    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"ok": False, "code": "os_unsupported"}))
    )
    assert checker.main(["check_native_helper.py", "foundation"]) == 1
    assert "macOS 26" in capsys.readouterr().err

    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert checker.main(["check_native_helper.py", "speech"]) == 1
    assert checker.main(["check_native_helper.py"]) == 2


def test_macos_version_probe_never_raises(monkeypatch):
    checker = _load_checker()

    def missing_sw_vers(*_args, **_kwargs):
        raise FileNotFoundError("sw_vers")

    monkeypatch.setattr(checker.subprocess, "run", missing_sw_vers)
    assert checker.macos_major_version() == 0


def test_every_helper_smoke_test_uses_the_checker():
    scripts = {
        name: (MACOS_ROOT / "scripts" / name).read_text(encoding="utf-8")
        for name in (
            "build_dmg.sh",
            "build_foundation_helper.sh",
            "build_speech_helper.sh",
        )
    }

    for name, script in scripts.items():
        assert "os_unsupported" not in script.replace(
            "# os_unsupported is only accepted on a runner older than macOS 26.", ""
        ), name
    assert scripts["build_dmg.sh"].count('check_native_helper.py" speech') == 1
    assert scripts["build_dmg.sh"].count('check_native_helper.py" foundation') == 1
    assert 'check_native_helper.py" foundation' in scripts["build_foundation_helper.sh"]
    assert 'check_native_helper.py" speech' in scripts["build_speech_helper.sh"]


def test_helpers_really_run_on_a_macos_26_runner_without_gating_releases():
    workflows = MACOS_ROOT.parent / ".github" / "workflows"
    workflow = (workflows / "native-helpers.yml").read_text(encoding="utf-8")
    triggers, jobs = workflow.split("\njobs:")

    # On macOS 26 the checker refuses os_unsupported: the Swift code past the
    # availability guard is executed, which the macOS 15 DMG jobs never do.
    assert "runs-on: macos-26" in jobs
    assert "bash scripts/build_speech_helper.sh" in jobs
    assert "bash scripts/build_foundation_helper.sh" in jobs
    for name in ("build_speech_helper.sh", "build_foundation_helper.sh"):
        assert (MACOS_ROOT / "scripts" / name).is_file()
    for trigger in ("schedule:", "workflow_dispatch:", "- macos/native/**"):
        assert trigger in triggers

    # Informative and read-only: no secret, no write access, no blocking.
    assert "continue-on-error: true" in jobs
    assert "permissions:\n  contents: read" in triggers
    assert "contents: write" not in workflow
    assert "secrets." not in workflow
    assert "persist-credentials: false" in jobs
    assert "${{" not in jobs
    # The releases only follow the CI workflow, never this one.
    beta = (workflows / "beta-release.yml").read_text(encoding="utf-8")
    assert re.search(r"workflows:\n\s+- CI\n\s+types:", beta)

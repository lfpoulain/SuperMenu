import os
import re
import sys
from pathlib import Path

from src.config import build_info
from src.utils import paths


def test_resource_path_uses_pyinstaller_extraction_directory(monkeypatch, tmp_path):
    extraction_dir = tmp_path / "_MEI123"
    extraction_dir.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(extraction_dir), raising=False)

    assert paths.resource_path("bin", "ffmpeg.exe") == os.path.join(
        str(extraction_dir), "bin", "ffmpeg.exe"
    )


def test_packaged_smoke_check_requires_icon_and_ffmpeg(monkeypatch, tmp_path):
    icon = tmp_path / "resources" / "icons" / "icon.png"
    ffmpeg = tmp_path / "bin" / "ffmpeg.exe"
    icon.parent.mkdir(parents=True)
    ffmpeg.parent.mkdir(parents=True)
    icon.write_bytes(b"icon")
    ffmpeg.write_bytes(b"exe")
    monkeypatch.setattr(paths, "application_base_dir", lambda: str(tmp_path))

    result = paths.packaged_resource_status()

    assert result["ok"] is True
    assert result["icon"] == str(icon)
    assert result["ffmpeg"] == str(ffmpeg)


def test_installer_does_not_duplicate_one_file_resources():
    content = Path(paths.resource_path("setup_supermenu.iss")).read_text(
        encoding="utf-8"
    )

    assert 'Source: "bin\\*"' not in content
    assert 'Source: "resources\\*"' not in content
    assert "MyOutputBaseFilename" in content


def test_release_version_and_default_channel_are_valid():
    root = Path(paths.resource_path())
    version = (root / "VERSION").read_text(encoding="utf-8").strip()

    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    assert build_info.APP_VERSION == "dev"
    assert build_info.BUILD_CHANNEL == "stable"


def test_release_workflows_keep_ci_beta_and_stable_separate():
    workflows = Path(paths.resource_path(".github", "workflows"))
    ci = (workflows / "ci.yml").read_text(encoding="utf-8")
    beta = (workflows / "beta-release.yml").read_text(encoding="utf-8")
    stable = (workflows / "stable-release.yml").read_text(encoding="utf-8")

    assert "pull_request:" in ci
    assert "workflow_run:" in beta
    assert "github.event.workflow_run.conclusion == 'success'" in beta
    assert "schedule:" not in beta
    assert "tag: beta" in beta
    assert "SuperMenu_Beta_Setup.exe" in beta
    assert "update-beta.json" in beta
    assert 'tags:\n      - "v*.*.*"' in stable
    assert "immutableCreate: true" in stable
    assert "updateOnlyUnreleased: true" in stable
    assert "update-stable.json" in stable

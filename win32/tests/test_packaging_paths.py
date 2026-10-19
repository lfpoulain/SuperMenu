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

    assert paths.resource_path("resources", "icons", "icon.png") == os.path.join(
        str(extraction_dir), "resources", "icons", "icon.png"
    )


def test_packaged_smoke_check_requires_the_application_icon(monkeypatch, tmp_path):
    icon = tmp_path / "resources" / "icons" / "icon.png"
    icon.parent.mkdir(parents=True)
    icon.write_bytes(b"icon")
    monkeypatch.setattr(paths, "application_base_dir", lambda: str(tmp_path))

    result = paths.packaged_resource_status()

    assert result["ok"] is True
    assert result["icon"] == str(icon)


def test_installer_does_not_duplicate_one_file_resources():
    content = Path(paths.resource_path("setup_supermenu.iss")).read_text(
        encoding="utf-8"
    )

    assert 'Source: "resources\\*"' not in content
    assert '[InstallDelete]' in content
    assert 'Type: filesandordirs; Name: "{app}\\bin"' in content
    assert "MyOutputBaseFilename" in content
    assert "LicenseFile=..\\LICENSE" in content
    assert (Path(paths.application_base_dir()).parent / "LICENSE").is_file()


def test_installer_ships_the_license_and_third_party_notices():
    content = Path(paths.resource_path("setup_supermenu.iss")).read_text(
        encoding="utf-8"
    )
    files = content.split("[Files]", 1)[1].split("\n[", 1)[0]

    # The AppId identifies existing installations: it must never change.
    assert "AppId={{C8F9E2A0-1F3A-4E5D-B6A9-D5C8E4E0F2A1}" in content
    assert "DefaultDirName={autopf}\\{#MyAppName}" in content
    assert '#define MyAppPublisher "LFPoulain"' in content
    assert '#define MyAppURL "https://github.com/lfpoulain/SuperMenu"' in content
    for directive in ("AppPublisherURL=", "AppSupportURL=", "AppUpdatesURL="):
        assert f"{directive}{{#MyAppURL}}" in content
    assert 'Source: "..\\LICENSE"; DestDir: "{app}"' in files
    assert 'Source: "..\\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"' in files
    assert 'Source: "..\\licenses\\*.txt"; DestDir: "{app}\\licenses"' in files
    generated = next(
        line for line in files.splitlines()
        if line.startswith('Source: "dist\\third_party_licenses\\*"')
    )
    # The folder comes from the PyInstaller build: compiling the installer
    # without it must still work.
    assert "skipifsourcedoesntexist" in generated
    assert "recursesubdirs" in generated
    assert 'Type: filesandordirs; Name: "{app}\\third_party_licenses"' in content


def test_windows_bundle_collects_the_license_files():
    repository = Path(paths.application_base_dir()).parent
    spec = (repository / "win32" / "SuperMenu.spec").read_text(encoding="utf-8")

    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "licenses"):
        assert f"(str(repository_dir / '{name}'), " in spec
        assert (repository / name).exists()
    assert '"tools" / "collect_third_party_licenses.py"' in spec
    assert "license_collector.pyinstaller_datas(" in spec
    # Written next to the executable, where the installer picks it up.
    assert 'Path(DISTPATH) / "third_party_licenses"' in spec
    assert 'requirement_files=[project_dir / "requirements.txt"]' in spec
    # Collected after Analysis (it needs its TOC) and before the executable.
    assert spec.index("a = Analysis(") < spec.index("a.datas += license_collector")
    assert spec.index("a.datas += license_collector") < spec.index("exe = EXE(")


def test_pyinstaller_specs_include_the_shared_package_path():
    repository = Path(paths.application_base_dir()).parent
    windows_spec = (repository / "win32" / "SuperMenu.spec").read_text(encoding="utf-8")
    macos_spec = (repository / "macos" / "SuperMenu-macos.spec").read_text(
        encoding="utf-8"
    )

    assert 'project_dir.parent / "shared"' in windows_spec
    assert 'project_dir.parent / "shared"' in macos_spec
    assert "str(shared_dir)" in windows_spec
    assert "str(shared_dir)" in macos_spec


def test_release_version_and_default_channel_are_valid():
    root = Path(paths.resource_path())
    version = (root / "VERSION").read_text(encoding="utf-8").strip()

    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    assert build_info.APP_VERSION == "dev"
    assert build_info.BUILD_CHANNEL == "stable"


# workflow_run's branches filter matches head_branch, which a pull request from
# a fork's main also sets: every beta job must require a push to main here.
# A fork keeps the workflow file but has no secrets: it must start nothing.
TRUSTED_REPOSITORY = "github.repository == 'lfpoulain/SuperMenu'"
TRUSTED_BETA_CONDITION = (
    f"{TRUSTED_REPOSITORY} && "
    "((github.event_name == 'workflow_run' && "
    "github.event.workflow_run.conclusion == 'success' && "
    "github.event.workflow_run.event == 'push' && "
    "github.event.workflow_run.head_branch == 'main' && "
    "github.event.workflow_run.head_repository.full_name == github.repository) || "
    "(github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'))"
)


def _workflow(name):
    workflows = Path(paths.application_base_dir()).parent / ".github" / "workflows"
    return (workflows / name).read_text(encoding="utf-8")


def _job(workflow, name):
    match = re.search(rf"^  {name}:\n(.*?)(?=^  \S|\Z)", workflow, re.M | re.S)
    assert match, f"{name} job not found"
    return match.group(1)


def _job_condition(job):
    match = re.search(r"^    if: >-\n((?:      .*\n)+)", job, re.M)
    assert match, "job has no folded if: condition"
    return " ".join(match.group(1).split())


def _run_scripts(workflow):
    lines = workflow.splitlines()
    scripts = []
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("run:"):
            continue
        value = stripped[len("run:") :].strip()
        if value and value not in ("|", "|-", ">", ">-"):
            scripts.append(value)
            continue
        indent = len(line) - len(stripped)
        block = []
        for following in lines[index + 1 :]:
            if following.strip() and len(following) - len(following.lstrip()) <= indent:
                break
            block.append(following)
        scripts.append("\n".join(block))
    return scripts


def test_release_workflows_keep_ci_beta_and_stable_separate():
    workflows = Path(paths.application_base_dir()).parent / ".github" / "workflows"
    ci = (workflows / "ci.yml").read_text(encoding="utf-8")
    beta = (workflows / "beta-release.yml").read_text(encoding="utf-8")
    stable = (workflows / "stable-release.yml").read_text(encoding="utf-8")

    assert "pull_request:" in ci
    assert "workflow_run:" in beta
    assert "github.event.workflow_run.conclusion == 'success'" in beta
    assert "schedule:" not in beta
    assert 'releases/tags/beta"' in beta
    assert "gh release upload beta " in beta
    assert "SuperMenu_Beta_Setup.exe" in beta
    assert "update-beta.json" in beta
    assert beta.index("Validate source") < beta.index(
        "Inject Windows beta metadata"
    )
    assert 'git tag --force beta "${BUILD_COMMIT}"' in beta
    assert "git push --force origin refs/tags/beta" in beta
    assert beta.index("Publish rolling beta prerelease") < beta.index(
        "Align rolling beta tag with published commit"
    )
    assert 'tags:\n      - "v*.*.*"' in stable
    assert "immutableCreate: true" in stable
    assert "updateOnlyUnreleased: true" in stable
    assert "update-stable.json" in stable
    assert stable.index("Validate source") < stable.index(
        "Inject Windows stable metadata"
    )


def test_beta_release_only_builds_commits_pushed_to_main():
    beta = _workflow("beta-release.yml")
    triggers = beta.split("\npermissions:")[0]

    assert "workflow_run:" in triggers
    assert "push:" not in triggers
    assert "pull_request" not in triggers
    assert "github.event_name == 'push'" not in beta
    for job_name in ("build-windows-beta", "build-macos-beta", "publish-beta"):
        assert _job_condition(_job(beta, job_name)) == TRUSTED_BETA_CONDITION


def test_stable_release_starts_nothing_in_a_fork():
    stable = _workflow("stable-release.yml")

    assert _job(stable, "validate-stable").startswith(f"    if: {TRUSTED_REPOSITORY}\n")
    # The other jobs inherit the guard: a job whose need is skipped is skipped.
    for job_name in ("build-windows-stable", "build-macos-stable"):
        assert _job(stable, job_name).startswith("    needs: validate-stable\n")
    publish = _job(stable, "publish-stable")
    assert "      - validate-stable\n" in publish
    assert "if:" not in publish.split("steps:")[0]


def test_release_workflows_grant_write_access_only_to_publication():
    for workflow_name, build_jobs, publish_job in (
        (
            "beta-release.yml",
            ("build-windows-beta", "build-macos-beta"),
            "publish-beta",
        ),
        (
            "stable-release.yml",
            ("build-windows-stable", "build-macos-stable"),
            "publish-stable",
        ),
    ):
        workflow = _workflow(workflow_name)

        assert "permissions:\n  contents: read" in workflow.split("\njobs:")[0]
        assert workflow.count("contents: write") == 1
        # The OIDC token and the attestation write only serve the provenance
        # attestation of the published files.
        assert (
            "permissions:\n      contents: write\n"
            "      id-token: write\n      attestations: write\n"
        ) in _job(workflow, publish_job)
        assert workflow.count("id-token: write") == 1
        assert workflow.count("attestations: write") == 1
        for job_name in build_jobs:
            job = _job(workflow, job_name)
            assert job.count("uses: actions/checkout@") == 1
            assert "persist-credentials: false" in job


def test_workflow_scripts_read_github_context_from_the_environment():
    # ${{ }} is pasted into the script before the shell parses it, so a tag or
    # branch name could inject commands; scripts read env variables instead.
    for workflow_name in ("ci.yml", "beta-release.yml", "stable-release.yml"):
        scripts = _run_scripts(_workflow(workflow_name))
        assert scripts
        for script in scripts:
            assert "${{" not in script, f"{workflow_name}: {script}"

    assert "$tag = $env:GITHUB_REF_NAME" in _workflow("stable-release.yml")


def test_macos_pull_requests_build_a_test_dmg():
    workflow = (
        Path(paths.application_base_dir()).parent / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    # An exact job name: "build-dmg:" alone would also match "macos-build-dmg:".
    dmg_job = _job(workflow, "macos-build-dmg")
    assert "scripts/build_dmg.sh" in dmg_job
    assert "if:" not in dmg_job.split("steps:")[0]
    # A test DMG: no Apple secret, and no notarization that an Apple outage
    # could turn red. Signing belongs to the beta and stable workflows.
    assert "secrets." not in workflow
    assert "notarize_dmg.sh" not in dmg_job
    assert "MACOS_" not in dmg_job
    assert "SuperMenu-macOS-arm64-unsigned-test" in dmg_job
    assert workflow.count("persist-credentials: false") == workflow.count(
        "uses: actions/checkout@"
    )
    # SuperMenu is distributed for Apple Silicon only; the slice is part of
    # the artifact name so an Intel user cannot pick up a bundle that will
    # not launch.
    assert "macos/dist/SuperMenu-*-macOS-arm64.dmg" in workflow


def test_release_workflows_pin_every_action_by_commit():
    # These workflows hold the Apple certificate or a write token: a moved tag
    # must not change the code they run. Dependabot updates SHA and comment.
    for workflow_name in ("beta-release.yml", "stable-release.yml"):
        actions = re.findall(r"^ +(?:- )?uses: (.+)$", _workflow(workflow_name), re.M)
        assert actions
        for action in actions:
            assert re.fullmatch(
                r"[\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+", action
            ), f"{workflow_name}: {action}"


def test_release_installers_use_a_fixed_inno_setup():
    for workflow_name, job_name in (
        ("beta-release.yml", "build-windows-beta"),
        ("stable-release.yml", "build-windows-stable"),
    ):
        job = _job(_workflow(workflow_name), job_name)

        assert re.search(r"^      INNO_SETUP_VERSION: \d+\.\d+\.\d+$", job, re.M)
        assert "choco install innosetup --version $env:INNO_SETUP_VERSION" in job
        assert '-ne "innosetup|$env:INNO_SETUP_VERSION"' in job
        assert "choco install innosetup --no-progress" not in job

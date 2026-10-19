"""Release workflows: beta publication order, installer fingerprints and
release notes read by the updater."""

import re
from pathlib import Path

from src.utils import paths
from src.utils import updater


REPOSITORY = Path(paths.application_base_dir()).parent


def _workflow(name):
    return (REPOSITORY / ".github" / "workflows" / name).read_text(encoding="utf-8")


def _job(workflow, name):
    match = re.search(rf"^  {name}:\n(.*?)(?=^  \S|\Z)", workflow, re.M | re.S)
    assert match, f"{name} job not found"
    return match.group(1)


def _step_script(workflow, step_name):
    match = re.search(
        rf"^      - name: {re.escape(step_name)}\n(.*?)(?=^      - name: |^  \S|\Z)",
        workflow,
        re.M | re.S,
    )
    assert match, f"{step_name} step not found"
    script = match.group(1).split("run: |\n", 1)[1]
    return "\n".join(line[10:] for line in script.splitlines())


def _render_notes(script, notes_text, env):
    """Rebuild the release body exactly as the cat/printf lines produce it."""
    output = []
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("cat "):
            output.append(notes_text)
        elif stripped.startswith("printf "):
            match = re.fullmatch(
                r"printf (?:-- )?'([^']*)'((?:\s+\"\$\{\w+\}\")*)",
                stripped,
            )
            assert match, f"printf line not understood: {stripped}"
            fmt = match.group(1).replace("\\n", "\n")
            names = re.findall(r"\$\{(\w+)\}", match.group(2))
            output.append(fmt % tuple(env[name] for name in names))
    return "".join(output)


def test_beta_publication_is_never_cancelled_halfway():
    beta = _workflow("beta-release.yml")

    # A run-level group would let any newer run, even one whose jobs are all
    # skipped, cancel the publication in the middle of the asset swap.
    assert "concurrency:" not in beta.split("\njobs:")[0]
    publish = _job(beta, "publish-beta")
    assert "concurrency:\n      group: beta-release-publish\n      cancel-in-progress: false" in publish
    for job_name in ("build-windows-beta", "build-macos-beta"):
        assert "cancel-in-progress: true" in _job(beta, job_name)


def test_beta_assets_are_staged_then_swapped_with_manifests_last():
    beta = _workflow("beta-release.yml")
    script = _step_script(beta, "Publish rolling beta prerelease")

    assert "removeArtifacts:" not in beta
    assert "ncipollo/release-action" not in _job(beta, "publish-beta")
    assets = re.search(r"final_assets=\(\n(.*?)\n\)", script, re.S).group(1).split()
    assert assets[-2:] == ["update-beta.json", "update-macos-beta.json"]
    for installer in (
        "SuperMenu_Beta.exe",
        "SuperMenu_Beta_Setup.exe",
        "SuperMenu_Beta-macOS-arm64.dmg",
    ):
        assert assets.index(installer) < assets.index("update-beta.json")

    upload = script.index('gh release upload beta "${staging_dir}"/*')
    delete_old = script.index('releases/assets/${old_id}"')
    rename = script.index('releases/assets/${staged_ids[${index}]}"')
    assert script.index("Asset beta manquant") < upload < delete_old < rename
    assert "set -euo pipefail" in script
    assert beta.index("Publish rolling beta prerelease") < beta.index(
        "Align rolling beta tag with published commit"
    )


def test_published_manifests_carry_the_installer_sha256():
    for workflow_name, installer, dmg in (
        ("beta-release.yml", "SuperMenu_Beta_Setup.exe", "SuperMenu_Beta-macOS-arm64.dmg"),
        ("stable-release.yml", "SuperMenu_Setup.exe", "SuperMenu-macOS-arm64.dmg"),
    ):
        script = _step_script(
            _workflow(workflow_name), "Generate platform manifests and checksums"
        )

        assert "set -euo pipefail" in script
        assert f'windows_sha256="$(sha256sum {installer} | cut -d \' \' -f 1)"' in script
        assert f'macos_sha256="$(sha256sum {dmg} | cut -d \' \' -f 1)"' in script
        assert f'asset: "{installer}", sha256: $sha256}}' in script
        assert f'asset: "{dmg}", sha256: $sha256}}' in script
        assert '--arg sha256 "${windows_sha256}"' in script
        assert '--arg sha256 "${macos_sha256}"' in script


def test_beta_notes_keep_the_version_lines_read_by_the_updater():
    beta = _workflow("beta-release.yml")
    notes = (REPOSITORY / ".github" / "BETA_NOTES.md").read_text(encoding="utf-8")
    env = {
        "WINDOWS_VERSION": "1.2.2-beta.71",
        "MACOS_VERSION": "1.2.9-beta.71",
        "BUILD_COMMIT": "0123abc",
    }

    body = _render_notes(_step_script(beta, "Prepare concise beta notes"), notes, env)

    assert "- Windows version: 1.2.2-beta.71\n" in body
    assert "- macOS version: 1.2.9-beta.71\n" in body
    assert updater.extract_version_from_release(
        {"name": "SuperMenu Beta", "tag_name": "beta", "body": body}
    ) == "1.2.2-beta.71"


def test_beta_body_already_published_without_metadata_lines_is_understood():
    body = (
        "## Nouveautés de cette bêta\n\n- Choix du modèle.\n\n"
        "Windows : `1.2.2-beta.61` · macOS Apple Silicon : `1.2.9-beta.61`\n"
        "\n<details>\n<summary>Informations de build</summary>\n\n"
        "Commit : `abc`\n\n</details>\n"
    )

    assert updater.extract_version_from_release(
        {"name": "SuperMenu Beta", "tag_name": "beta", "body": body}
    ) == "1.2.2-beta.61"


def test_stable_notes_come_from_a_versioned_file():
    stable = _workflow("stable-release.yml")
    publish = _job(stable, "publish-stable")
    notes_path = REPOSITORY / ".github" / "STABLE_NOTES.md"

    assert notes_path.is_file()
    assert "bodyFile: stable-release-notes.md" in publish
    assert "body: |" not in stable
    assert "sparse-checkout: .github" in publish
    assert "persist-credentials: false" in publish

    body = _render_notes(
        _step_script(stable, "Prepare stable notes"),
        notes_path.read_text(encoding="utf-8"),
        {"WINDOWS_VERSION": "1.2.2", "MACOS_VERSION": "1.2.9", "GITHUB_SHA": "abc"},
    )
    assert updater.extract_version_from_release(
        {"name": "SuperMenu 1.2.2", "tag_name": "v1.2.2", "body": body}
    ) == "1.2.2"
    assert "- Channel: stable\n" in body


def test_stable_tag_and_notes_are_checked_before_both_builds():
    stable = _workflow("stable-release.yml")
    validate = _job(stable, "validate-stable")
    script = _step_script(stable, "Validate stable tag and notes")

    # A short Linux job: neither the Windows build nor the macOS signing and
    # notarization start when the tag or the notes are wrong.
    assert "runs-on: ubuntu-latest" in validate
    assert "persist-credentials: false" in validate
    assert "secrets." not in validate
    for job_name in ("build-windows-stable", "build-macos-stable"):
        assert _job(stable, job_name).startswith("    needs: validate-stable\n")

    assert "set -euo pipefail" in script
    assert '"${GITHUB_REF_NAME}" =~ ^v([0-9]+\\.[0-9]+\\.[0-9]+)$' in script
    assert "tr -d '[:space:]' < win32/VERSION" in script
    assert script.count("exit 1") == 3


def test_stable_tag_must_point_to_main_and_bump_macos():
    stable = _workflow("stable-release.yml")
    validate = _job(stable, "validate-stable")
    script = _step_script(stable, "Validate stable tag and notes")

    # The full history, so origin/main is there to compare the tag with.
    assert "fetch-depth: 0" in validate
    assert (
        'git merge-base --is-ancestor "${GITHUB_SHA}" refs/remotes/origin/main'
        in script
    )
    # A heading naming the version, not a substring: 1.2.1 is quoted in the
    # 1.3.0 notes, and would also be found in 1.2.10.
    assert "grep -qF" not in script
    assert (
        'python3 tools/release_guard.py notes-heading "${app_version}" '
        ".github/STABLE_NOTES.md" in script
    )
    assert 'macos_version="$(tr -d \'[:space:]\' < macos/VERSION)"' in script
    assert (
        'release_guard.py require-newer "${macos_version}" '
        '"${latest_url}/update-macos-stable.json"' in script
    )
    assert (
        'latest_url="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/releases/latest/download"'
        in script
    )


def test_latest_badge_is_computed_not_forced():
    stable = _workflow("stable-release.yml")
    validate = _job(stable, "validate-stable")
    script = _step_script(stable, "Validate stable tag and notes")
    publish = _job(stable, "publish-stable")

    assert "makeLatest: true" not in stable
    assert (
        'release_guard.py make-latest "${app_version}" "${latest_url}/update-stable.json"'
        in script
    )
    assert 'echo "make_latest=${make_latest}" >> "${GITHUB_OUTPUT}"' in script
    assert "make_latest: ${{ steps.validate.outputs.make_latest }}" in validate
    assert "makeLatest: ${{ needs.validate-stable.outputs.make_latest }}" in publish


def test_beta_versions_must_outrank_the_published_releases():
    beta = _workflow("beta-release.yml")
    windows = _job(beta, "build-windows-beta")
    macos = _job(beta, "build-macos-beta")
    windows_check = _step_script(beta, "Check Windows beta version against the published beta")
    macos_check = _step_script(beta, "Check macOS beta version against published releases")
    releases = "${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/releases"

    # vX.Y.Z already released means win32/VERSION was not bumped: the beta
    # would rank below the stable for every updater.
    metadata = _step_script(beta, "Prepare Windows beta metadata")
    assert 'if (git tag --list "v$baseVersion") {' in metadata
    assert metadata.index("git tag --list") < metadata.index("APP_VERSION=")

    assert (
        '$manifestUrl = "$env:GITHUB_SERVER_URL/$env:GITHUB_REPOSITORY'
        '/releases/download/beta/update-beta.json"' in windows_check
    )
    assert "python ../tools/release_guard.py require-newer $env:APP_VERSION $manifestUrl" in windows_check
    # PowerShell does not stop on a failing native command by itself.
    assert "if ($LASTEXITCODE -ne 0) {" in windows_check

    assert "set -euo pipefail" in macos_check
    for manifest in (
        "download/beta/update-macos-beta.json",
        "latest/download/update-macos-stable.json",
    ):
        assert (
            f'python ../tools/release_guard.py require-newer "${{APP_VERSION}}" '
            f'"${{releases_url}}/{manifest}"' in macos_check
        )
    assert f'releases_url="{releases}"' in macos_check

    # Checked before the tests and the notarization: a wrong number costs a
    # minute, not a build.
    for job, check in (
        (windows, "Check Windows beta version"),
        (macos, "Check macOS beta version"),
    ):
        assert job.index("Set up Python") < job.index(check) < job.index("Install dependencies")
    assert macos.index("Check macOS beta version") < macos.index("scripts/notarize_dmg.sh")


def test_published_files_carry_a_provenance_attestation():
    for workflow_name, publish_job, publish_step in (
        ("beta-release.yml", "publish-beta", "Publish rolling beta prerelease"),
        ("stable-release.yml", "publish-stable", "Publish stable release"),
    ):
        workflow = _workflow(workflow_name)
        job = _job(workflow, publish_job)

        assert workflow.count("actions/attest-build-provenance@") == 1
        assert "actions/attest-build-provenance@" in job
        assert "subject-path: release-assets/*" in job
        # The manifests and checksums are attested too, and nothing is
        # published when the attestation fails.
        assert (
            job.index("Generate platform manifests and checksums")
            < job.index("Attest build provenance")
            < job.index(publish_step)
        )

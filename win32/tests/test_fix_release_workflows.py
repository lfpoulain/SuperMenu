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
        rf"^      - name: {re.escape(step_name)}\n(.*?)(?=^      - name: |\Z)",
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
    assert 'grep -qF -- "${app_version}" .github/STABLE_NOTES.md' in script
    assert script.count("exit 1") == 3

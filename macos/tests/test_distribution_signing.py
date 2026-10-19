import ast
import plistlib
import re
from pathlib import Path


MACOS_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = MACOS_ROOT.parent


def _script(*parts: str) -> str:
    return (MACOS_ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def _commands(script: str) -> str:
    """Drop comment lines so assertions read the commands, not the rationale."""
    return "\n".join(
        line for line in script.splitlines() if not line.lstrip().startswith("#")
    )


def _job(workflow: str, name: str) -> str:
    match = re.search(rf"^  {name}:\n(.*?)(?=^  \S|\Z)", workflow, re.M | re.S)
    assert match, f"{name} job not found"
    return match.group(1)


def test_pyinstaller_uses_optional_developer_id_identity():
    spec = (MACOS_ROOT / "SuperMenu-macos.spec").read_text(encoding="utf-8")

    assert 'os.environ.get("MACOS_CODESIGN_IDENTITY")' in spec
    assert "codesign_identity=codesign_identity" in spec


def test_hardened_runtime_ships_the_entitlements_it_requires():
    """PyInstaller passes --options=runtime, which needs these exceptions.

    PyObjC builds Objective-C blocks from Python callables through libffi
    closures. Without allow-unsigned-executable-memory the Hardened Runtime
    kills the process when the global key monitor installs its handler.
    """
    spec = (MACOS_ROOT / "SuperMenu-macos.spec").read_text(encoding="utf-8")
    entitlements_path = MACOS_ROOT / "entitlements.plist"

    assert 'entitlements_file=str(project_dir / "entitlements.plist")' in spec
    assert entitlements_path.is_file()

    entitlements = plistlib.loads(entitlements_path.read_bytes())
    for key in (
        "com.apple.security.cs.allow-jit",
        "com.apple.security.cs.allow-unsigned-executable-memory",
        "com.apple.security.cs.disable-library-validation",
    ):
        assert entitlements[key] is True


def test_entitlements_stay_parseable_by_codesign():
    """Well-formedness is the guard that matters here.

    A first version documented the keys in place and codesign rejected it with
    "AMFIUnserializeXML: syntax error near line 6", because the comment
    contained "--options=runtime" and a double hyphen is illegal inside an XML
    comment. plistlib fails on the same line, so parsing the file is enough to
    catch it. Keeping the plist comment-free removes the class of problem, and
    the rationale for each key lives in docs/ARCHITECTURE.md.
    """
    raw = (MACOS_ROOT / "entitlements.plist").read_bytes()

    assert isinstance(plistlib.loads(raw), dict)
    assert b"<!--" not in raw
    assert b"\r\n" not in raw


def test_app_bundle_ships_the_license_and_third_party_notices():
    spec = (MACOS_ROOT / "SuperMenu-macos.spec").read_text(encoding="utf-8")
    build = _commands(_script("scripts", "build_dmg.sh"))

    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "licenses"):
        assert f'(str(repository_dir / "{name}"), ' in spec
        assert (REPOSITORY_ROOT / name).exists()
    assert '"tools" / "collect_third_party_licenses.py"' in spec
    assert "license_collector.pyinstaller_datas(" in spec
    # Nothing outside the .app needs the generated folder on macOS.
    assert 'Path(workpath) / "third_party_licenses"' in spec
    assert 'requirement_files=[project_dir / "requirements.txt"]' in spec
    assert spec.index("a = Analysis(") < spec.index("a.datas += license_collector")
    assert spec.index("a.datas += license_collector") < spec.index("coll = COLLECT(")

    # The packaged app is checked before it is signed into a DMG.
    assert "Contents/Resources/${notice}" in build
    for notice in ("LICENSE", "THIRD_PARTY_NOTICES.md", "licenses/LGPL-3.0.txt"):
        assert notice in build
    assert build.index("Contents/Resources/${notice}") < build.index("hdiutil create")


def _spec_filter():
    """Load _is_shipped from the spec without running PyInstaller."""
    spec = (MACOS_ROOT / "SuperMenu-macos.spec").read_text(encoding="utf-8")
    tree = ast.parse(spec)
    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"_is_shipped_path", "_is_shipped"}
    ]
    namespace = {"Path": Path}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "spec", "exec"), namespace)
    return namespace["_is_shipped"]


def test_excluded_qt_components_leave_no_dangling_symlink():
    """A top-level link to a dropped framework made codesign reject the bundle.

    PyInstaller links QtPdf.framework's binary into the top-level directory
    for the PDF plugin's dependency; once the framework was dropped, the link
    dangled in Contents/Frameworks and Contents/Resources.
    """
    is_shipped = _spec_filter()
    framework = "PySide6/Qt/lib/QtPdf.framework/Versions/A/QtPdf"

    assert not is_shipped((framework, "/site-packages/" + framework, "BINARY"))
    assert not is_shipped(("QtPdf", framework, "SYMLINK"))
    assert not is_shipped(
        ("PySide6/Qt/plugins/imageformats/libqpdf.dylib", "/x/libqpdf.dylib", "BINARY")
    )
    assert not is_shipped((
        "QtVirtualKeyboard",
        "PySide6/Qt/lib/QtVirtualKeyboard.framework/Versions/A/QtVirtualKeyboard",
        "SYMLINK",
    ))
    assert is_shipped((
        "QtGui",
        "PySide6/Qt/lib/QtGui.framework/Versions/A/QtGui",
        "SYMLINK",
    ))
    assert is_shipped(("VERSION", "/x/VERSION", "DATA"))


def test_build_rejects_a_bundle_with_a_dangling_symlink():
    """CI builds unsigned, so codesign never runs there: check the links."""
    build = _commands(_script("scripts", "build_dmg.sh"))

    check = build.index("find \"${app_path}\" -type l ! -exec test -e {} \\; -print")
    assert check < build.index('if [[ -n "${MACOS_CODESIGN_IDENTITY:-}" ]]; then')
    assert check < build.index("--smoke-test")


def test_build_targets_apple_silicon_only():
    spec = (MACOS_ROOT / "SuperMenu-macos.spec").read_text(encoding="utf-8")

    assert 'target_arch="arm64"' in spec


def test_packaged_smoke_test_exercises_the_pyobjc_block_path():
    """The entitlement failure is a crash, not an exception.

    Only running the code path on the signed binary can catch it, so the
    smoke test must install the native monitors before the DMG is published.
    """
    run_py = (MACOS_ROOT / "run.py").read_text(encoding="utf-8")

    assert "probe_native_hotkey_support" in run_py
    assert "native_hotkey_probe_ok" in run_py


def test_distribution_scripts_sign_notarize_and_staple_the_dmg():
    build = _commands(_script("scripts", "build_dmg.sh"))
    notarize = _script("scripts", "notarize.sh")
    notarize_dmg = _script("scripts", "notarize_dmg.sh")

    # --deep is deprecated by Apple; a strict top-level verification is what
    # the signature actually needs to satisfy.
    assert "--deep" not in build
    assert "codesign --verify --strict" in build
    assert '--sign "${MACOS_CODESIGN_IDENTITY}"' in build
    assert "xcrun notarytool submit" in notarize
    assert "xcrun stapler staple" in notarize
    assert "spctl --assess" in notarize
    assert "notarize.sh" in notarize_dmg


def test_the_app_bundle_is_stapled_before_it_is_packaged():
    """A DMG ticket does not follow the app into /Applications.

    Without a ticket on the bundle itself, the first launch needs a live
    Gatekeeper round trip and fails offline.
    """
    build = _commands(_script("scripts", "build_dmg.sh"))
    notarize = _script("scripts", "notarize.sh")

    staple_app = build.index('notarize.sh" "${app_path}"')
    create_dmg = build.index("hdiutil create")
    assert staple_app < create_dmg

    # notarytool refuses a bare bundle, and plain zip corrupts the signature.
    assert "ditto -c -k --keepParent" in notarize
    # The staged copy must keep the ticket, so cp -R is not acceptable here.
    assert "cp -R" not in build


def test_stapling_retries_a_transient_apple_failure():
    """An Accepted notarization can still fail to staple (stapler error 68,
    "network connection was lost") while Apple's ticket service catches up:
    retry before failing. Stapling validates the ticket itself, so no extra
    `stapler validate` round trip can fail a notarization that succeeded;
    the offline Gatekeeper assessment is the final check."""
    notarize = _commands(_script("scripts", "notarize.sh"))

    assert "for attempt in 1 2 3 4 5; do" in notarize
    assert 'if xcrun stapler staple "${artifact_path}"; then' in notarize
    assert "sleep $((attempt * 20))" in notarize
    retry = notarize.index("for attempt in 1 2 3 4 5; do")
    assert notarize.index("xcrun notarytool submit") < retry
    assert retry < notarize.index("spctl --assess")
    assert notarize.count("xcrun stapler staple") == 1
    assert "stapler validate" not in notarize


def test_ci_builds_an_unsigned_dmg_without_apple_credentials():
    """Every push used to notarize a test DMG, and an Apple outage (code 68)
    turned main red. CI never sees the Apple secrets now."""
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    dmg_job = _job(workflow, "macos-build-dmg")

    assert "secrets." not in workflow
    assert "MACOS_" not in workflow.replace("DEVELOPER_DIR", "")
    assert "security import" not in workflow
    assert "notarize_dmg.sh" not in workflow
    assert "signed-notarized" not in workflow
    assert "scripts/build_dmg.sh" in dmg_job
    assert "name: SuperMenu-macOS-arm64-unsigned-test" in dmg_job


def test_beta_and_stable_releases_require_a_notarized_macos_dmg():
    workflows_dir = REPOSITORY_ROOT / ".github" / "workflows"
    beta = (workflows_dir / "beta-release.yml").read_text(encoding="utf-8")
    stable = (workflows_dir / "stable-release.yml").read_text(
        encoding="utf-8"
    )

    for workflow in (beta, stable):
        for secret_name in (
            "MACOS_CERTIFICATE_BASE64",
            "MACOS_CERTIFICATE_PASSWORD",
            "MACOS_APPLE_ID",
            "MACOS_APP_PASSWORD",
            "MACOS_TEAM_ID",
        ):
            assert f"secrets.{secret_name}" in workflow
        assert "scripts/build_dmg.sh" in workflow
        assert "scripts/notarize_dmg.sh" in workflow
        assert "security delete-keychain" in workflow
        assert "if: always()" in workflow
        assert "macOS-arm64.dmg" in workflow
        assert "update-macos-" in workflow

    assert "needs.build-macos-beta.outputs.app_version" in beta
    assert "needs.build-macos-stable.outputs.app_version" in stable
    assert "SuperMenu_Beta-macOS-arm64.dmg" in beta
    assert "SuperMenu-macOS-arm64.dmg" in stable
    assert beta.index("Validate source") < beta.index(
        "Inject macOS beta metadata"
    )
    assert stable.index("Validate source") < stable.index(
        "Inject macOS stable metadata"
    )


def test_apple_secrets_reach_only_trusted_commits_without_a_write_token():
    workflows_dir = REPOSITORY_ROOT / ".github" / "workflows"
    beta = (workflows_dir / "beta-release.yml").read_text(encoding="utf-8")
    stable = (workflows_dir / "stable-release.yml").read_text(encoding="utf-8")

    for workflow, job_name in (
        (beta, "build-macos-beta"),
        (stable, "build-macos-stable"),
    ):
        job = _job(workflow, job_name)
        # The signing job is the only one that sees the Apple secrets, and it
        # neither holds a write token nor leaves one in .git/config.
        assert "secrets.MACOS_CERTIFICATE_BASE64" in job
        assert workflow.count("secrets.MACOS_") == job.count("secrets.MACOS_")
        assert "permissions:\n  contents: read" in workflow.split("\njobs:")[0]
        assert "contents: write" not in job
        assert "persist-credentials: false" in job

    # workflow_run also fires for pull requests, including one opened from a
    # fork's main: only a CI run for a push to main here may build the beta.
    beta_job = _job(beta, "build-macos-beta")
    assert "push:" not in beta.split("\npermissions:")[0]
    for guard in (
        "github.repository == 'lfpoulain/SuperMenu'",
        "github.event.workflow_run.conclusion == 'success'",
        "github.event.workflow_run.event == 'push'",
        "github.event.workflow_run.head_branch == 'main'",
        "github.event.workflow_run.head_repository.full_name == github.repository",
    ):
        assert guard in beta_job

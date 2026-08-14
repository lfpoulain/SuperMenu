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

    entitlements = entitlements_path.read_text(encoding="utf-8")
    for key in (
        "com.apple.security.cs.allow-jit",
        "com.apple.security.cs.allow-unsigned-executable-memory",
        "com.apple.security.cs.disable-library-validation",
    ):
        assert key in entitlements


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
    assert "xcrun stapler validate" in notarize
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


def test_ci_keeps_apple_credentials_in_secrets_and_cleans_the_keychain():
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    for secret_name in (
        "MACOS_CERTIFICATE_BASE64",
        "MACOS_CERTIFICATE_PASSWORD",
        "MACOS_APPLE_ID",
        "MACOS_APP_PASSWORD",
        "MACOS_TEAM_ID",
    ):
        assert f"secrets.{secret_name}" in workflow
    assert "security import" in workflow
    assert "scripts/notarize_dmg.sh" in workflow
    assert "signed-notarized" in workflow
    assert "unsigned-test" in workflow
    assert "security delete-keychain" in workflow
    assert "if: always()" in workflow

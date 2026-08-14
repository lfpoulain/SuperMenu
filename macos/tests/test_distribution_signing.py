from pathlib import Path


MACOS_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = MACOS_ROOT.parent


def test_pyinstaller_uses_optional_developer_id_identity():
    spec = (MACOS_ROOT / "SuperMenu-macos.spec").read_text(encoding="utf-8")

    assert 'os.environ.get("MACOS_CODESIGN_IDENTITY")' in spec
    assert "codesign_identity=codesign_identity" in spec


def test_distribution_scripts_sign_notarize_and_staple_the_dmg():
    build = (MACOS_ROOT / "scripts" / "build_dmg.sh").read_text(encoding="utf-8")
    notarize = (MACOS_ROOT / "scripts" / "notarize_dmg.sh").read_text(
        encoding="utf-8"
    )

    assert "codesign --verify --deep --strict" in build
    assert '--sign "${MACOS_CODESIGN_IDENTITY}"' in build
    assert "xcrun notarytool submit" in notarize
    assert "xcrun stapler staple" in notarize
    assert "xcrun stapler validate" in notarize
    assert "spctl --assess" in notarize


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

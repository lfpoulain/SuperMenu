#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
version="$(tr -d '[:space:]' < "${project_dir}/VERSION")"
app_path="${project_dir}/dist/SuperMenu.app"
# SuperMenu is distributed for Apple Silicon only; the slice is part of the
# artifact name so an Intel user never downloads a bundle that cannot launch.
dmg_path="${project_dir}/dist/SuperMenu-${version}-macOS-arm64.dmg"

cd "${project_dir}"
bash "${script_dir}/create_icon.sh"
python -m PyInstaller --noconfirm --clean SuperMenu-macos.spec

if [[ -n "${MACOS_CODESIGN_IDENTITY:-}" ]]; then
    # --deep is deprecated by Apple for both signing and verification.
    # PyInstaller already signs every nested Mach-O, so a strict top-level
    # verification is what actually needs to hold here.
    codesign --verify --strict --verbose=4 "${app_path}"
    codesign --display --verbose=4 "${app_path}"
fi

"${app_path}/Contents/MacOS/SuperMenu" --smoke-test

# Notarize and staple the bundle before it is packaged, so the ticket survives
# the drag to /Applications and the first launch works offline.
if [[ -n "${MACOS_CODESIGN_IDENTITY:-}" && -n "${MACOS_APPLE_ID:-}" ]]; then
    bash "${script_dir}/notarize.sh" "${app_path}"
fi

staging_dir="$(mktemp -d "${TMPDIR:-/tmp}/supermenu-dmg.XXXXXX")"
trap 'rm -rf "${staging_dir}"' EXIT
# ditto, not cp -R: it is Apple's bundle-safe copy and preserves the signature,
# extended attributes and the notarization ticket stapled just above.
ditto "${app_path}" "${staging_dir}/SuperMenu.app"
ln -s /Applications "${staging_dir}/Applications"
rm -f "${dmg_path}"
hdiutil create \
    -volname "SuperMenu" \
    -srcfolder "${staging_dir}" \
    -ov \
    -format UDZO \
    "${dmg_path}"

if [[ -n "${MACOS_CODESIGN_IDENTITY:-}" ]]; then
    codesign \
        --force \
        --sign "${MACOS_CODESIGN_IDENTITY}" \
        --timestamp \
        "${dmg_path}"
    codesign --verify --strict --verbose=2 "${dmg_path}"
fi

echo "DMG créé : ${dmg_path}"

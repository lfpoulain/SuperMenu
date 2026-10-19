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
bash "${script_dir}/build_foundation_helper.sh"
bash "${script_dir}/build_speech_helper.sh"
python -m PyInstaller --noconfirm --clean SuperMenu-macos.spec

if [[ -n "${MACOS_CODESIGN_IDENTITY:-}" ]]; then
    # --deep is deprecated by Apple for both signing and verification.
    # PyInstaller already signs every nested Mach-O, so a strict top-level
    # verification is what actually needs to hold here.
    codesign --verify --strict --verbose=4 "${app_path}"
    codesign --display --verbose=4 "${app_path}"
fi

"${app_path}/Contents/MacOS/SuperMenu" --smoke-test

# PyInstaller places collected data files in Contents/Resources. The license
# and the third-party notices must travel with every copy of the app.
for notice in LICENSE THIRD_PARTY_NOTICES.md licenses/LGPL-3.0.txt; do
    if [[ ! -f "${app_path}/Contents/Resources/${notice}" ]]; then
        echo "Fichier de licence absent de l'application : ${notice}" >&2
        exit 1
    fi
done

# os_unsupported is only accepted on a runner older than macOS 26.
printf '%s\n' '{"action":"probe","language":"fr"}' | \
    "${app_path}/Contents/Frameworks/native/SuperMenuSpeech" | \
    python "${script_dir}/check_native_helper.py" speech

# Exercise the signed, bundled helper before notarizing and publishing it.
printf '%s' '{"action":"availability"}' | \
    "${app_path}/Contents/Frameworks/native/SuperMenuFoundationModels" | \
    python "${script_dir}/check_native_helper.py" foundation

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
# Hosted macOS runners can briefly report "Resource busy" when creating a DMG.
# Retry the packaging command, but always fail before signing if none succeeds.
for attempt in 1 2 3; do
    if hdiutil create \
        -volname "SuperMenu" \
        -srcfolder "${staging_dir}" \
        -ov \
        -format UDZO \
        "${dmg_path}"; then
        break
    fi
    if [[ "${attempt}" -eq 3 ]]; then
        echo "Impossible de créer le DMG après trois tentatives." >&2
        exit 1
    fi
    sleep 5
done

if [[ -n "${MACOS_CODESIGN_IDENTITY:-}" ]]; then
    codesign \
        --force \
        --sign "${MACOS_CODESIGN_IDENTITY}" \
        --timestamp \
        "${dmg_path}"
    codesign --verify --strict --verbose=2 "${dmg_path}"
fi

echo "DMG créé : ${dmg_path}"

#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
version="$(tr -d '[:space:]' < "${project_dir}/VERSION")"
app_path="${project_dir}/dist/SuperMenu.app"
dmg_path="${project_dir}/dist/SuperMenu-${version}-macOS.dmg"

cd "${project_dir}"
bash "${script_dir}/create_icon.sh"
python -m PyInstaller --noconfirm --clean SuperMenu-macos.spec

if [[ -n "${MACOS_CODESIGN_IDENTITY:-}" ]]; then
    codesign --verify --deep --strict --verbose=2 "${app_path}"
    codesign --display --verbose=4 "${app_path}"
fi

"${app_path}/Contents/MacOS/SuperMenu" --smoke-test

staging_dir="$(mktemp -d "${TMPDIR:-/tmp}/supermenu-dmg.XXXXXX")"
trap 'rm -rf "${staging_dir}"' EXIT
cp -R "${app_path}" "${staging_dir}/SuperMenu.app"
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

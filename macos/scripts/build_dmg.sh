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

echo "DMG créé : ${dmg_path}"

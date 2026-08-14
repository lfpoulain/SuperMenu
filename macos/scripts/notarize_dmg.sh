#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
version="$(tr -d '[:space:]' < "${project_dir}/VERSION")"
dmg_path="${1:-${project_dir}/dist/SuperMenu-${version}-macOS.dmg}"

for variable_name in MACOS_APPLE_ID MACOS_APP_PASSWORD MACOS_TEAM_ID; do
    if [[ -z "${!variable_name:-}" ]]; then
        echo "Variable requise absente : ${variable_name}" >&2
        exit 1
    fi
done

if [[ ! -f "${dmg_path}" ]]; then
    echo "DMG introuvable : ${dmg_path}" >&2
    exit 1
fi

xcrun notarytool submit "${dmg_path}" \
    --apple-id "${MACOS_APPLE_ID}" \
    --password "${MACOS_APP_PASSWORD}" \
    --team-id "${MACOS_TEAM_ID}" \
    --wait \
    --timeout 60m

xcrun stapler staple "${dmg_path}"
xcrun stapler validate "${dmg_path}"
spctl --assess \
    --type open \
    --context context:primary-signature \
    --verbose=2 \
    "${dmg_path}"

echo "DMG notarié et validé : ${dmg_path}"

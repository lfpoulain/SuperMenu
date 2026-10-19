#!/usr/bin/env bash
# Notarize and staple the distribution DMG.
#
# The .app inside was already notarized and stapled by build_dmg.sh, so this
# step only covers the disk image itself.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
version="$(tr -d '[:space:]' < "${project_dir}/VERSION")"
dmg_path="${1:-${project_dir}/dist/SuperMenu-${version}-macOS-arm64.dmg}"

bash "${script_dir}/notarize.sh" "${dmg_path}"

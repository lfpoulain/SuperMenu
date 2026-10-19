#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
source_icon="${project_dir}/resources/icons/icon.png"
iconset_dir="${project_dir}/build/SuperMenu.iconset"
output_icon="${project_dir}/resources/icons/app_icon.icns"

mkdir -p "${project_dir}/build"
rm -rf "${iconset_dir}"
mkdir -p "${iconset_dir}"

sips -z 16 16 "${source_icon}" --out "${iconset_dir}/icon_16x16.png" >/dev/null
sips -z 32 32 "${source_icon}" --out "${iconset_dir}/icon_16x16@2x.png" >/dev/null
sips -z 32 32 "${source_icon}" --out "${iconset_dir}/icon_32x32.png" >/dev/null
sips -z 64 64 "${source_icon}" --out "${iconset_dir}/icon_32x32@2x.png" >/dev/null
sips -z 128 128 "${source_icon}" --out "${iconset_dir}/icon_128x128.png" >/dev/null
sips -z 256 256 "${source_icon}" --out "${iconset_dir}/icon_128x128@2x.png" >/dev/null
sips -z 256 256 "${source_icon}" --out "${iconset_dir}/icon_256x256.png" >/dev/null
sips -z 512 512 "${source_icon}" --out "${iconset_dir}/icon_256x256@2x.png" >/dev/null
sips -z 512 512 "${source_icon}" --out "${iconset_dir}/icon_512x512.png" >/dev/null
sips -z 1024 1024 "${source_icon}" --out "${iconset_dir}/icon_512x512@2x.png" >/dev/null
iconutil -c icns "${iconset_dir}" -o "${output_icon}"


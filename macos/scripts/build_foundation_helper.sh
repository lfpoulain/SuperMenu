#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
output_dir="${project_dir}/build/native"
sdk_version="$(xcrun --sdk macosx --show-sdk-version)"
if [[ "${sdk_version%%.*}" -lt 26 ]]; then
    echo "Foundation Models nécessite Xcode 26+ (SDK macOS 26+)." >&2
    exit 1
fi
mkdir -p "${output_dir}"
# Keep the helper launchable on older macOS versions so its availability check
# works there too. All Foundation Models calls are guarded and weak-linked.
xcrun swiftc \
    -parse-as-library -O \
    -target arm64-apple-macos12.0 \
    -sdk "$(xcrun --sdk macosx --show-sdk-path)" \
    -weak_framework FoundationModels \
    "${project_dir}/native/FoundationModelsHelper.swift" \
    -o "${output_dir}/SuperMenuFoundationModels"

printf '%s' '{"action":"availability"}' | "${output_dir}/SuperMenuFoundationModels" | \
    python -c 'import json, sys; r = json.load(sys.stdin); assert type(r.get("ok")) is bool; assert r["ok"] or r.get("code") in {"os_unsupported", "device_not_eligible", "intelligence_disabled", "model_not_ready", "unavailable"}, r'

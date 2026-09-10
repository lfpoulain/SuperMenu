#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
mkdir -p "${project_dir}/build/native"
xcrun swiftc -parse-as-library -O -target arm64-apple-macos12.0 \
    -sdk "$(xcrun --sdk macosx --show-sdk-path)" \
    -Xlinker -weak_framework -Xlinker Speech \
    "${project_dir}/native/SpeechHelper.swift" \
    -o "${project_dir}/build/native/SuperMenuSpeech"
printf '%s\n' '{"action":"probe","language":"fr"}' | \
    "${project_dir}/build/native/SuperMenuSpeech" | \
    python -c 'import json, sys; r = json.load(sys.stdin); assert r.get("event") == "result" or r.get("code") == "os_unsupported", r'

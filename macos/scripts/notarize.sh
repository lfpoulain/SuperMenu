#!/usr/bin/env bash
# Submit one artifact to Apple, wait for the verdict, then staple its ticket.
#
# Accepts either the .app bundle or the DMG. notarytool only takes zip, pkg and
# dmg uploads, so a bundle is wrapped with ditto before submission; the ticket
# is still stapled onto the bundle itself. Stapling the .app matters: a DMG
# ticket does not travel with the app once it is dragged to /Applications, so
# without it the first launch needs a live Gatekeeper round trip.
set -euo pipefail

artifact_path="${1:?Usage: notarize.sh <chemin .app ou .dmg>}"

for variable_name in MACOS_APPLE_ID MACOS_APP_PASSWORD MACOS_TEAM_ID; do
    if [[ -z "${!variable_name:-}" ]]; then
        echo "Variable requise absente : ${variable_name}" >&2
        exit 1
    fi
done

if [[ ! -e "${artifact_path}" ]]; then
    echo "Artifact introuvable : ${artifact_path}" >&2
    exit 1
fi

upload_path="${artifact_path}"
cleanup_path=""
assess_args=(--type open --context context:primary-signature)

if [[ "${artifact_path}" == *.app ]]; then
    cleanup_path="$(mktemp -d "${TMPDIR:-/tmp}/supermenu-notarize.XXXXXX")"
    upload_path="${cleanup_path}/$(basename "${artifact_path}").zip"
    # ditto preserves the bundle's symlinks and extended attributes; `zip`
    # would corrupt the signature.
    ditto -c -k --keepParent "${artifact_path}" "${upload_path}"
    # Bash 3.2 (shipped with macOS) treats an empty array as unset with -u.
    assess_args=(--type exec)
fi

trap '[[ -n "${cleanup_path}" ]] && rm -rf "${cleanup_path}"' EXIT

xcrun notarytool submit "${upload_path}" \
    --apple-id "${MACOS_APPLE_ID}" \
    --password "${MACOS_APP_PASSWORD}" \
    --team-id "${MACOS_TEAM_ID}" \
    --no-s3-acceleration \
    --wait \
    --timeout 20m

xcrun stapler staple "${artifact_path}"
xcrun stapler validate "${artifact_path}"
spctl --assess \
    "${assess_args[@]}" \
    --verbose=2 \
    "${artifact_path}"

echo "Notarié et agrafé : ${artifact_path}"

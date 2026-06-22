#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${HOME}/Applications/NiederDaily.app"
CONTENTS_DIR="${APP_DIR}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
RESOURCES_DIR="${CONTENTS_DIR}/Resources"
INFO_TEMPLATE="${REPO_DIR}/setup/NiederDaily.app.Info.plist.template"
LAUNCHER_TEMPLATE="${REPO_DIR}/setup/NiederDailyLauncher.swift.template"
TMP_SWIFT_BASE="$(mktemp -t niederdaily-launcher)"
TMP_SWIFT="${TMP_SWIFT_BASE}.swift"
ICON_SCRIPT="${REPO_DIR}/setup/generate_niederdaily_icon.swift"
ICON_TMP_DIR="$(mktemp -d -t niederdaily-icon)"
ICONSET_DIR="${ICON_TMP_DIR}/AppIcon.iconset"

cleanup() {
  rm -f "${TMP_SWIFT_BASE}" "${TMP_SWIFT}"
  rm -rf "${ICON_TMP_DIR}"
}

trap cleanup EXIT

mkdir -p "${MACOS_DIR}" "${RESOURCES_DIR}"
mkdir -p "${ICONSET_DIR}"

PYTHON_PATH="${REPO_DIR}/.venv/bin/python"
SCRIPT_PATH="${REPO_DIR}/niederdaily.py"
LAUNCHER_PATH="${MACOS_DIR}/NiederDaily"

sed \
  -e "s|__REPO_DIR__|${REPO_DIR}|g" \
  -e "s|__PYTHON_PATH__|${PYTHON_PATH}|g" \
  -e "s|__SCRIPT_PATH__|${SCRIPT_PATH}|g" \
  "${LAUNCHER_TEMPLATE}" > "${TMP_SWIFT}"

xcrun swiftc "${TMP_SWIFT}" -O -o "${LAUNCHER_PATH}"
chmod +x "${LAUNCHER_PATH}"
cp "${INFO_TEMPLATE}" "${CONTENTS_DIR}/Info.plist"
xcrun swift "${ICON_SCRIPT}" "${ICONSET_DIR}"
iconutil -c icns "${ICONSET_DIR}" -o "${RESOURCES_DIR}/AppIcon.icns"
touch "${APP_DIR}"

# --- Code signing -------------------------------------------------------------
# Sign with a STABLE identity so macOS privacy (TCC) grants -- Calendar,
# Reminders, and Full Disk Access (Messages chat.db) -- survive rebuilds.
# swiftc applies an ad-hoc signature whose cdhash changes on every build, which
# silently revokes those grants for the scheduled launchd run (the app then
# can't read calendar/messages and the morning digest loses all personal
# context). A stable cert keeps the designated requirement constant across
# rebuilds and annual cert renewals, so the grant persists.
SIGN_IDENTITY="${NIEDERDAILY_SIGN_IDENTITY:-Apple Development: John Niedermeyer (9473SD42A5)}"
if security find-identity -v -p codesigning | grep -qF "${SIGN_IDENTITY}"; then
  codesign --force --sign "${SIGN_IDENTITY}" \
    --identifier me.nieder.NiederDaily --timestamp=none "${APP_DIR}"
  codesign --verify --strict "${APP_DIR}"
  echo "Signed ${APP_DIR} with: ${SIGN_IDENTITY}"
else
  echo "WARNING: signing identity '${SIGN_IDENTITY}' not found." >&2
  echo "         App is ad-hoc signed and will LOSE Calendar/Reminders/Messages" >&2
  echo "         TCC grants on the next rebuild. Set NIEDERDAILY_SIGN_IDENTITY to override." >&2
fi

echo "Built ${APP_DIR}"
echo "Run with macOS privacy permissions:"
echo "  open -W -n -gj \"${APP_DIR}\" --args --run"

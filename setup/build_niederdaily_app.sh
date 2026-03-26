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

echo "Built ${APP_DIR}"

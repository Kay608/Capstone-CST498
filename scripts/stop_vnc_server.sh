#!/usr/bin/env bash
set -euo pipefail

DISPLAY_NUM="${DISPLAY_NUM:-1}"
NOVNC_PORT="${NOVNC_PORT:-6080}"

if command -v tigervncserver >/dev/null 2>&1; then
    VNC_CMD="tigervncserver"
elif command -v vncserver >/dev/null 2>&1; then
    VNC_CMD="vncserver"
else
    VNC_CMD=""
fi

pkill -f "websockify .*:${NOVNC_PORT}" >/dev/null 2>&1 || true

if [[ -n "${VNC_CMD}" ]]; then
    "${VNC_CMD}" -kill ":${DISPLAY_NUM}" >/dev/null 2>&1 || true
fi

echo "Stopped VNC display :${DISPLAY_NUM} and websockify on port ${NOVNC_PORT}"
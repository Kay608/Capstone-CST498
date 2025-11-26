#!/usr/bin/env bash
set -euo pipefail

DISPLAY_NUM="${DISPLAY_NUM:-1}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
VNC_LOG="/tmp/vncserver_${DISPLAY_NUM}.log"
NOVNC_LOG="/tmp/novnc_${NOVNC_PORT}.log"

if command -v tigervncserver >/dev/null 2>&1; then
    VNC_CMD="tigervncserver"
elif command -v vncserver >/dev/null 2>&1; then
    VNC_CMD="vncserver"
else
    echo "tigervncserver or vncserver not found in PATH" >&2
    exit 1
fi

"${VNC_CMD}" -kill ":${DISPLAY_NUM}" >/dev/null 2>&1 || true
"${VNC_CMD}" -localhost no ":${DISPLAY_NUM}" >"${VNC_LOG}" 2>&1

if ! pgrep -f "websockify .*:${NOVNC_PORT}" >/dev/null 2>&1; then
    nohup websockify --web=/usr/share/novnc/ "${NOVNC_PORT}" "localhost:$((5900 + DISPLAY_NUM))" >"${NOVNC_LOG}" 2>&1 &
    echo "websockify started on port ${NOVNC_PORT}"
else
    echo "websockify already running on port ${NOVNC_PORT}"
fi

echo "VNC server ready on :${DISPLAY_NUM}; access via http://<host>:${NOVNC_PORT}"

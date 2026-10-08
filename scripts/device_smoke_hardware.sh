#!/bin/sh
# Run the opt-in app-level SM-T820 smoke through the existing device container.
set -eu
task_workspace=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -n "${SERIAL:-}" ]; then
    set -- --serial "$SERIAL"
else
    set --
fi
exec sh "$task_workspace/scripts/device.sh" exec \
    python3 /workspace/scripts/device_smoke_hardware.py "$@" \
    --suite media --suite gpu --suite audio-route --suite webview --suite vulkan

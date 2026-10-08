#!/bin/sh
# Pass an optional host SERIAL into the device tools container without shell interpolation.
set -eu
task_workspace=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -n "${SERIAL:-}" ]; then
    set -- --serial "$SERIAL"
else
    set --
fi
exec sh "$task_workspace/scripts/device.sh" exec \
    python3 /workspace/scripts/device_smoke.py "$@"

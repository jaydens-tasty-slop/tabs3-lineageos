#!/bin/sh
set -eu
task_workspace=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
task_profile=${1:-quick}
case "$task_profile" in quick|full|browser) ;; *)
    printf '%s\n' 'Usage: sh scripts/device_qualification.sh {quick|full|browser}' >&2
    exit 2;;
esac
task_serial=${SERIAL:-}
if [ -z "$task_serial" ]; then
    task_serials=$(sh "$task_workspace/scripts/device.sh" adb devices | awk 'NR > 1 && $2 == "device" { print $1 }')
    set -- $task_serials
    if [ "$#" -ne 1 ]; then
        printf '%s\n' 'Connect exactly one authorized device or set SERIAL=<adb-serial>.' >&2
        exit 2
    fi
    task_serial=$1
fi
if [ "$task_profile" = browser ]; then
    sh "$task_workspace/scripts/device.sh" exec python3 scripts/device_fdroid_install.py \
        --serial "$task_serial" --payloads artifacts/fdroid-apps --reuse-identical
fi
exec sh "$task_workspace/scripts/device.sh" exec python3 scripts/run_qualification.py \
    --profile "$task_profile" --serial "$task_serial"

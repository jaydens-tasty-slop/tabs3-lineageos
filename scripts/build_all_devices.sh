#!/usr/bin/env bash
# Build one ZIP per tablet in a single run. Each device is built in its own
# shell so product selection and lunch state cannot leak between them. A
# failure on one device does not prevent the others from being built.
# Set TAB_S3_DEVICES to build a subset, for example TAB_S3_DEVICES=gts3llte.
set -eo pipefail
rm -f /workspace/state/build-rom.exit
failed=
for device in ${TAB_S3_DEVICES:-gts3lwifi gts3llte}; do
    printf '=== Building %s ===\n' "$device"
    if ! TAB_S3_DEVICE=$device bash /workspace/scripts/build_device.sh "$@"; then
        failed="$failed $device"
    fi
done
if [[ -n $failed ]]; then
    printf 'Build failed for:%s\n' "$failed" >&2
    exit 1
fi

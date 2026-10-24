#!/usr/bin/env bash
# Resume the OTA targets using the existing Android output and Ninja graph.
set -eo pipefail
TAB_S3_MAKE_JOBS=8 exec bash /workspace/scripts/build_all_devices.sh "$@"

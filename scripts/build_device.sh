#!/usr/bin/env bash
# Build and package one tablet. TAB_S3_DEVICE selects gts3lwifi (default) or gts3llte.
# Extra arguments are passed to m before the otapackage target.
set -eo pipefail
source /workspace/scripts/build_env.sh
nice -n 15 ionice -c 3 m "-j${TAB_S3_MAKE_JOBS:-24}" "TARGET_KERNEL_ADDITIONAL_FLAGS=$TAB_S3_KERNEL_MAKE_FLAGS" "$@" otapackage
# Build only the host tools needed for the offline release audit.
nice -n 15 ionice -c 3 m -j8 deapexer out/host/linux-x86/bin/debugfs_static out/host/linux-x86/bin/simg2img
source /workspace/scripts/finalize_rom.sh

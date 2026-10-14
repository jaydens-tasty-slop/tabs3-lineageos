#!/usr/bin/env bash
set -eo pipefail
rm -f /workspace/state/build-rom.exit
source /workspace/scripts/build_env.sh
nice -n 15 ionice -c 3 m -j24 "TARGET_KERNEL_ADDITIONAL_FLAGS=$TAB_S3_KERNEL_MAKE_FLAGS" otapackage
# Build only the host tools needed for the offline release audit.
nice -n 15 ionice -c 3 m -j8 deapexer out/host/linux-x86/bin/debugfs_static out/host/linux-x86/bin/simg2img
source /workspace/scripts/finalize_rom.sh

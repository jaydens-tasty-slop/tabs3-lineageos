#!/usr/bin/env bash
set -eo pipefail
rm -f /workspace/state/build-rom.exit
source /workspace/scripts/build_env.sh
m -j24 bacon
# Build the source-owned tools used by the final offline vendor inventory.
m -j8 deapexer out/host/linux-x86/bin/debugfs_static

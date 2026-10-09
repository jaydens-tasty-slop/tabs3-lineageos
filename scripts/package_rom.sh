#!/usr/bin/env bash
# Resume the OTA target using the existing Android output and Ninja graph.
set -eo pipefail
rm -f /workspace/state/build-rom.exit
source /workspace/scripts/build_env.sh
m -j8 "$@" otapackage
m -j8 deapexer out/host/linux-x86/bin/debugfs_static out/host/linux-x86/bin/simg2img
source /workspace/scripts/finalize_rom.sh

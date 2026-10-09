#!/usr/bin/env bash
# Source from either build entry point; paths are stable across containers.
cd /workspace/android
export GIT_CONFIG_GLOBAL=/workspace/state/gitconfig
export BUILD_USERNAME=rom-builder
export BUILD_HOSTNAME=podman
export USE_CCACHE=1
export CCACHE_EXEC=/usr/bin/ccache
export CCACHE_DIR=/workspace/state/ccache
export CCACHE_MAXSIZE=30G
export PYTHONDONTWRITEBYTECODE=1
ccache --set-config=max_size=30G
export MALLOC_ARENA_MAX=2
export GOMAXPROCS=8
export GOGC=25
export GOMEMLIMIT=24GiB
export JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=8
export NINJA_HIGHMEM_NUM_JOBS=1
export OUT_DIR=out
# Preserve the host-tool compatibility flags used for the maintained 3.18
# kernel. Keep these in each kernel recipe rather than depending on host PATH.
TAB_S3_KERNEL_MAKE_FLAGS=${TAB_S3_KERNEL_MAKE_FLAGS:-'-j8 HOSTCC="/usr/bin/gcc -B/usr/bin/" HOSTCXX="/usr/bin/g++ -B/usr/bin/" HOSTAR=/usr/bin/ar HOSTLD=/usr/bin/ld HOSTCFLAGS="-O2 -std=gnu89" HOSTLDFLAGS="" KBUILD_BUILD_USER=rom-builder KBUILD_BUILD_HOST=podman LOCALVERSION=+'}
export LINEAGE_VERSION_APPEND_TIME_OF_DAY=${LINEAGE_VERSION_APPEND_TIME_OF_DAY:-true}
source build/envsetup.sh
lunch lineage_gts3lwifi-bp4a-userdebug

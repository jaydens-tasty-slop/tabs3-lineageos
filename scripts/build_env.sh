#!/usr/bin/env bash
# Source from either build entry point; paths are stable across containers.
# Select the product with TAB_S3_DEVICE: gts3lwifi (SM-T820, default) or gts3llte (SM-T825).
TAB_S3_DEVICE=${TAB_S3_DEVICE:-gts3lwifi}
case "$TAB_S3_DEVICE" in
    gts3lwifi|gts3llte) ;;
    *) printf 'Unsupported TAB_S3_DEVICE: %s\n' "$TAB_S3_DEVICE" >&2; return 1 ;;
esac
export TAB_S3_DEVICE
# Devices whose release ZIP is named UNTESTED because no tablet has run it yet.
# Empty by default: a user reported the SM-T825 ZIP boots (modem still unverified).
export TAB_S3_UNTESTED_DEVICES=${TAB_S3_UNTESTED_DEVICES-}
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
export GOMAXPROCS=${GOMAXPROCS:-4}
export GOGC=${GOGC:-10}
export GOMEMLIMIT=${GOMEMLIMIT:-12GiB}
export SOONG_SKIP_IDE_DEP_FILES=${SOONG_SKIP_IDE_DEP_FILES:-true}
export SOONG_PARTIAL_ANALYSIS=${SOONG_PARTIAL_ANALYSIS:-lineage_${TAB_S3_DEVICE}_generated_device}
export JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=8
export NINJA_HIGHMEM_NUM_JOBS=1
export OUT_DIR=out
# Preserve the host-tool compatibility flags used for the maintained 3.18
# kernel. Keep these in each kernel recipe rather than depending on host PATH.
TAB_S3_KERNEL_MAKE_FLAGS=${TAB_S3_KERNEL_MAKE_FLAGS:-'-j8 HOSTCC="/usr/bin/gcc -B/usr/bin/" HOSTCXX="/usr/bin/g++ -B/usr/bin/" HOSTAR=/usr/bin/ar HOSTLD=/usr/bin/ld HOSTCFLAGS="-O2 -std=gnu89" HOSTLDFLAGS="" KBUILD_BUILD_USER=rom-builder KBUILD_BUILD_HOST=podman LOCALVERSION=+'}
export LINEAGE_VERSION_APPEND_TIME_OF_DAY=${LINEAGE_VERSION_APPEND_TIME_OF_DAY:-true}
source build/envsetup.sh
lunch "lineage_${TAB_S3_DEVICE}-cp2a-userdebug"
tab_s3_platform_version=$(get_build_var PLATFORM_VERSION)
if [[ $tab_s3_platform_version != 17 ]]; then
    printf 'Refusing to build from %s: expected Android 17, got PLATFORM_VERSION=%s\n' \
        "$PWD" "${tab_s3_platform_version:-unset}" >&2
    return 1
fi
unset tab_s3_platform_version

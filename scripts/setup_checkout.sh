#!/usr/bin/env bash
# Restore the pinned upstream checkout in a fresh workspace, inside Podman.
set -euo pipefail
cd /workspace
if [ -d android/.repo ]; then
    printf '%s\n' 'The checkout already exists. Reuse it; this setup script is for a fresh workspace.' >&2
    exit 1
fi
mkdir -p upstream android state logs research artifacts
export GIT_CONFIG_GLOBAL=/workspace/state/gitconfig
git config --global user.name "${TAB_S3_GIT_NAME:-jaydens-tasty-slop}"
git config --global user.email "${TAB_S3_GIT_EMAIL:-325336397+jaydens-tasty-slop@users.noreply.github.com}"
if [ ! -d upstream/git-repo/.git ]; then
    git clone --branch v2.68.1 https://gerrit.googlesource.com/git-repo upstream/git-repo
fi
python3 scripts/clone_upstreams.py
cd android
python3 /workspace/upstream/git-repo/repo init \
    -u https://github.com/LineageOS/android.git \
    -b 2a50ca061bffe4e73918ae2e0b99b7a05f647154 \
    --depth=1 --git-lfs --no-use-superproject --repo-rev=v2.68.1
# Keep the source snapshot separate from upstream's tracked manifest files.
cp /workspace/manifests/base-source-lock.xml .repo/manifests/tabs3-pinned.xml
python3 /workspace/upstream/git-repo/repo init -m tabs3-pinned.xml --repo-rev=v2.68.1
python3 /workspace/upstream/git-repo/repo sync \
    -c --no-tags --optimized-fetch --fail-fast -j6
python3 /workspace/scripts/apply_port.py

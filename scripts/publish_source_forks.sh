#!/usr/bin/env bash
# Publish audited Tab S3 source branches as genuine GitHub forks.
set -euo pipefail
umask 077
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OWNER="jaydens-tasty-slop"
AUTHOR_EMAIL="325336397+jaydens-tasty-slop@users.noreply.github.com"
SSH_COMMAND='ssh -i ~/.ssh/jaydens-tasty-slop -o IdentitiesOnly=yes'
BRANCH="tabs3/lineage-23.2"
CHECK_LOCAL=false
case "${1:-}" in
  '') ;;
  --check-local) CHECK_LOCAL=true ;;
  -h|--help)
    printf '%s\n' \
      'Usage: bash scripts/publish_source_forks.sh [--check-local]' \
      'Publish four audited device/kernel/vendor forks using gh and the configured SSH key.' \
      '--check-local checks identities, patch hashes and source trees without network or pushes.' \
      'Missing staging clones can be restored from the already published fork branches.' \
      'The build-root repository is published separately.'
    exit 0 ;;
  *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
esac
(( $# <= 1 )) || { printf '%s\n' 'Only one optional argument is accepted.' >&2; exit 2; }
command -v git >/dev/null
command -v sha256sum >/dev/null
if [[ "$CHECK_LOCAL" != true ]]; then
  command -v gh >/dev/null
  login="$(gh api user --jq .login)"
  [[ "$login" == "$OWNER" ]] || {
    printf 'Authenticated account is %s; expected %s.\n' "$login" "$OWNER" >&2; exit 1;
  }
fi
SPECS=(
  'awesometic/android_device_samsung_gts3l-common|tabs3-android_device_samsung_gts3l-common|device__samsung__gts3l-common|device/samsung/gts3l-common|9f9bfcecba0c0c9a9018a5fae746f0f83f905555|47a1d8752a48971843d950e4c149d0cbeeab7ea2|92f1916339caec063b885beddd3742e63ddfe55f|7c9bae2afb626e4a5900d96b46f98154d5e03dd2f87a37e0d730250fa21a0ff8'
  'awesometic/android_device_samsung_gts3lwifi|tabs3-android_device_samsung_gts3lwifi|device__samsung__gts3lwifi|device/samsung/gts3lwifi|efb09886713c80890457bcadb37bc8d186e5ff12|2584dfd45b958abde464a31a551659f183f01c30|7e56fa7ef736dc3e30d667881c7f0c2de351961e|20434f3c2621bdaaf06b3cdd1e991d9d432d51aa653695e341127d97938c148f'
  'awesometic/android_kernel_samsung_msm8996|tabs3-android_kernel_samsung_msm8996|kernel__samsung__msm8996|kernel/samsung/msm8996|f355ebdfddf9f138e1b9161db034f4b913963d22|1695e64f9a8deaf03d1526ad2d669a79b3b3d70e|42e410d4389e09a12ddb4c1d0e5e88abcbf03396|04722b9ce761a5c196b7a185ef958dd97d1bde12e37b22496621cbf11343e155'
  'awesometic/proprietary_vendor_samsung|tabs3-proprietary_vendor_samsung|vendor__samsung|vendor/samsung|f6a87c20eb410363d2fa0f9628b05d59169bfd00|e15e895cc40cd263ab63cb7b01b600b74c1d14a1|526da53500135cd9727cef923903fb6f4ce87dbb|5c2033d8465fbec39d2c4a79b1c25edba1da4547be9cbd6d36e5df54ae506dee'
)

git_remote() {
  git -C "$clone" -c core.sshCommand="$SSH_COMMAND -o BatchMode=yes -o ConnectTimeout=15" "$@"
}

fork_state() {
  gh api "repos/$destination" --jq '[.full_name, (.fork|tostring), (.parent.full_name // "")] | @tsv'
}

verify_fork() {
  local state expected
  state="$(fork_state)"
  expected="$destination$(printf '\ttrue\t%s' "$upstream")"
  [[ "${state,,}" == "${expected,,}" ]] || {
    printf '%s is not the expected GitHub fork of %s.\n' "$destination" "$upstream" >&2; exit 1;
  }
}

# Verify every local tree and commit identity before remote mutations.
for spec in "${SPECS[@]}"; do
  IFS='|' read -r upstream repo_name slug source_path expected_commit expected_tree upstream_base patch_sha <<< "$spec"
  clone="$TASK_ROOT/state/public-source-publish/clones/$slug"
  destination="$OWNER/$repo_name"
  url="git@github.com:$destination.git"
  if [[ ! -d "$clone/.git" ]]; then
    [[ "$CHECK_LOCAL" != true ]] || {
      printf 'Audited staging clone is missing: %s\n' "$clone" >&2; exit 1;
    }
    verify_fork
    mkdir -p "$(dirname "$clone")"
    git -c core.sshCommand="$SSH_COMMAND -o BatchMode=yes -o ConnectTimeout=15" \
      clone --single-branch --branch "$BRANCH" --no-tags "$url" "$clone"
  fi
  if [[ "$CHECK_LOCAL" != true ]]; then
    git -C "$clone" config user.name "$OWNER"
    git -C "$clone" config user.email "$AUTHOR_EMAIL"
    git -C "$clone" config core.sshCommand "$SSH_COMMAND"
    if git -C "$clone" remote get-url origin >/dev/null 2>&1; then
      git -C "$clone" remote set-url origin "$url"
    else
      git -C "$clone" remote add origin "$url"
    fi
    if ! git -C "$clone" remote get-url upstream >/dev/null 2>&1; then
      git -C "$clone" remote add upstream "https://github.com/$upstream.git"
    fi
  fi
  [[ "$(git -C "$clone" config user.name)" == "$OWNER" &&
     "$(git -C "$clone" config user.email)" == "$AUTHOR_EMAIL" &&
     "$(git -C "$clone" config core.sshCommand)" == "$SSH_COMMAND" &&
     "$(git -C "$clone" remote get-url origin)" == "$url" ]] || {
    printf 'Git identity/SSH/origin check failed: %s\n' "$clone" >&2; exit 1;
  }
  actual="$(git -C "$clone" rev-parse "refs/heads/$BRANCH")"
  tree="$(git -C "$clone" rev-parse "$actual^{tree}")"
  [[ "$actual" == "$expected_commit" && "$tree" == "$expected_tree" &&
     -z "$(git -C "$clone" status --porcelain)" ]] || {
    printf 'Staging commit/tree/cleanliness check failed: %s\n' "$upstream" >&2; exit 1;
  }
  git -C "$clone" merge-base --is-ancestor "$upstream_base" "$actual"
  identities="$(git -C "$clone" log "$upstream_base..$actual" --format='%an|%ae|%cn|%ce' | LC_ALL=C sort -u)"
  [[ "$identities" == "$OWNER|$AUTHOR_EMAIL|$OWNER|$AUTHOR_EMAIL" ]] || {
    printf 'Port commit identity check failed: %s\n' "$upstream" >&2; exit 1;
  }
  if git -C "$clone" log "$upstream_base..$actual" --format=%B | \
      grep -Eiq 'codex|co-authored-by|(^|[[:space:]])try[[:space:]]*[0-9]'; then
    printf 'Unexpected trial/attribution text in port history: %s\n' "$upstream" >&2; exit 1
  fi
  actual_patch="$(sha256sum "$TASK_ROOT/patches/$slug.patch")"
  [[ "${actual_patch%% *}" == "$patch_sha" ]] || {
    printf 'Canonical patch changed: %s\n' "$source_path" >&2; exit 1;
  }
  if [[ "$source_path" == device/samsung/gts3l-common ]] && \
      git -C "$clone" cat-file -e "$actual:configs/bringup-usb.rc" 2>/dev/null; then
    printf '%s\n' 'Temporary forced-ADB rule remains in prepared source.' >&2; exit 1
  fi
  printf 'Local source verified: %s (%s).\n' "$upstream" "$actual"
done
[[ "$CHECK_LOCAL" != true ]] || exit 0

# gh repo fork creates GitHub fork relationships; an ordinary repo would fail verification.
for spec in "${SPECS[@]}"; do
  IFS='|' read -r upstream repo_name slug source_path expected_commit expected_tree upstream_base patch_sha <<< "$spec"
  destination="$OWNER/$repo_name"
  if ! fork_state >/dev/null 2>&1; then
    printf 'Creating GitHub fork %s from %s.\n' "$destination" "$upstream"
    gh repo fork "$upstream" --fork-name "$repo_name" --clone=false
    ready=false
    for attempt in {1..30}; do
      if fork_state >/dev/null 2>&1; then ready=true; break; fi
      sleep 2
    done
    [[ "$ready" == true ]] || { printf 'Fork is not ready: %s\n' "$destination" >&2; exit 1; }
  fi
  verify_fork
done

# Refuse divergent branches before the first push, then recheck at each push.
for pass in preflight publish; do
  for spec in "${SPECS[@]}"; do
    IFS='|' read -r upstream repo_name slug source_path expected_commit expected_tree upstream_base patch_sha <<< "$spec"
    clone="$TASK_ROOT/state/public-source-publish/clones/$slug"
    destination="$OWNER/$repo_name"
    remote_line="$(git_remote ls-remote origin "refs/heads/$BRANCH")"
    remote_commit="${remote_line%%$'\t'*}"
    if [[ -n "$remote_commit" && "$remote_commit" != "$expected_commit" ]]; then
      git -C "$clone" merge-base --is-ancestor "$remote_commit" "$expected_commit" || {
        printf 'Refusing divergent branch in %s; no force push is used.\n' "$destination" >&2; exit 1;
      }
    fi
    [[ "$pass" == publish ]] || continue
    if [[ "$remote_commit" != "$expected_commit" ]]; then
      git_remote push --set-upstream --no-follow-tags --recurse-submodules=no \
        origin "refs/heads/$BRANCH:refs/heads/$BRANCH"
    fi
    verified="$(git_remote ls-remote origin "refs/heads/$BRANCH" | awk 'NR==1 {print $1}')"
    [[ "$verified" == "$expected_commit" ]] || { printf 'Remote SHA check failed: %s\n' "$destination" >&2; exit 1; }
    verify_fork
    gh repo edit "$destination" --default-branch "$BRANCH" \
      --description 'Samsung Galaxy Tab S3 SM-T820: LineageOS 23.2 / Android 16 port' \
      --add-topic galaxy-tab-s3 --add-topic sm-t820 --add-topic lineageos --add-topic android16
    printf '%s\t%s\t%s\n' "$destination" "$upstream" "$verified" \
      >> "$TASK_ROOT/state/public-source-publish/published.tsv"
    printf 'Published and verified https://github.com/%s/tree/%s (%s).\n' "$destination" "$BRANCH" "$verified"
  done
done

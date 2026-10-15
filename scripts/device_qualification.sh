#!/bin/sh
set -eu
task_workspace=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
task_profile=${1:-quick}
case "$task_profile" in quick|full|browser) ;; *)
    printf '%s\n' 'Usage: sh scripts/device_qualification.sh {quick|full|browser}' >&2
    exit 2;;
esac
command -v flock >/dev/null 2>&1 || {
    printf '%s\n' 'flock is required to serialize qualification runs.' >&2
    exit 2
}
mkdir -p "$task_workspace/state"
exec 9>"$task_workspace/state/qualification.lock"
if ! flock -n 9; then
    printf '%s\n' 'Another qualification run is active for this buildroot; wait for it to finish.' >&2
    exit 2
fi
task_serial=${SERIAL:-}
if [ -z "$task_serial" ]; then
    task_serials=$(sh "$task_workspace/scripts/device.sh" adb devices | awk 'NR > 1 && $2 == "device" { print $1 }')
    set -- $task_serials
    if [ "$#" -ne 1 ]; then
        printf '%s\n' 'Connect exactly one authorized device or set SERIAL=<adb-serial>.' >&2
        exit 2
    fi
    task_serial=$1
fi
if ! task_shell_uid=$(sh "$task_workspace/scripts/device.sh" adb -s "$task_serial" shell id -u 2>&1); then
    printf '%s\n' "$task_shell_uid" >&2
    printf '%s\n' 'Normal ADB shell is unavailable. During fresh Android 17 setup, an upstream restricted Trade-In Mode transport can appear as a device while rejecting ordinary shells. Complete setup/connectivity, enable USB debugging in Developer Options, and toggle it off/on if the host retained a stale transport.' >&2
    exit 2
fi
if [ "$task_shell_uid" != 2000 ]; then
    printf '%s\n' "Qualification requires ordinary shell ADB (uid 2000); received uid $task_shell_uid." >&2
    exit 2
fi
task_widevine_args=
case "${TAB_S3_PROVISION_WIDEVINE:-0}" in
    0) ;;
    1) task_widevine_args=--provision-widevine ;;
    *) printf '%s\n' 'TAB_S3_PROVISION_WIDEVINE must be 0 or 1.' >&2; exit 2;;
esac
if [ "$task_profile" = browser ]; then
    task_user_state=$(sh "$task_workspace/scripts/device.sh" adb -s "$task_serial" shell am get-started-user-state 0)
    task_window_policy=$(sh "$task_workspace/scripts/device.sh" adb -s "$task_serial" shell dumpsys window policy)
    if [ "$task_user_state" != RUNNING_UNLOCKED ] || \
       ! printf '%s\n' "$task_window_policy" | grep -Eq 'mIsShowing=false|^[[:space:]]*showing=false[[:space:]]*$'; then
        printf '%s\n' 'Wake and unlock the current screen normally before browser APK installation.' >&2
        exit 2
    fi
    task_stay_awake_original=$(sh "$task_workspace/scripts/device.sh" adb -s "$task_serial" shell settings get global stay_on_while_plugged_in)
    case "$task_stay_awake_original" in null|[0-7]) ;; *)
        printf '%s\n' "Unexpected USB stay-awake setting: $task_stay_awake_original" >&2
        exit 2;;
    esac
    restore_browser_stay_awake() {
        if [ "$task_stay_awake_original" = null ]; then
            sh "$task_workspace/scripts/device.sh" adb -s "$task_serial" shell settings delete global stay_on_while_plugged_in >/dev/null
        else
            sh "$task_workspace/scripts/device.sh" adb -s "$task_serial" shell settings put global stay_on_while_plugged_in "$task_stay_awake_original" >/dev/null
        fi
    }
    trap restore_browser_stay_awake EXIT HUP INT TERM
    sh "$task_workspace/scripts/device.sh" adb -s "$task_serial" shell settings put global stay_on_while_plugged_in 2 >/dev/null
    sh "$task_workspace/scripts/device.sh" exec python3 scripts/device_fdroid_install.py \
        --serial "$task_serial" --payloads artifacts/fdroid-apps --reuse-identical
    sh "$task_workspace/scripts/device.sh" exec python3 scripts/run_qualification.py \
        --profile "$task_profile" --serial "$task_serial" $task_widevine_args
    task_status=$?
    restore_browser_stay_awake
    trap - EXIT HUP INT TERM
    exit "$task_status"
fi
exec sh "$task_workspace/scripts/device.sh" exec python3 scripts/run_qualification.py \
    --profile "$task_profile" --serial "$task_serial" $task_widevine_args

#!/bin/sh
# Use host ADB when installed; Python/tools stay in rootless Podman.
# TAB_S3_ADB_BACKEND=usb keeps the standalone container USB server available.
set -eu
task_workspace=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
task_image=localhost/lineageos-gts3-device:ubuntu22.04
task_container=${TAB_S3_DEVICE_CONTAINER:-lineageos-gts3-device-tools}
task_action=${1:-devices}
if [ "$#" -gt 0 ]; then shift; fi
task_backend=${TAB_S3_ADB_BACKEND:-auto}
case "$task_backend" in
    auto)
        if command -v adb >/dev/null 2>&1; then task_backend=host; else task_backend=usb; fi
        ;;
    host|usb) ;;
    *) printf '%s\n' 'TAB_S3_ADB_BACKEND must be auto, host, or usb.' >&2; exit 2;;
esac

task_save_public_key() {
    # Only export the public key for optional TWRP authorization after a wipe.
    # The host server continues to manage its own private key.
    if [ "$task_backend" = host ]; then
        task_public_key=${TAB_S3_HOST_ADB_PUBLIC_KEY:-"$HOME/.android/adbkey.pub"}
    else
        task_public_key=$task_workspace/state/device-adb/adbkey.pub
        # Older container ADB writes the private key but may omit its .pub file.
        # A recent host client can export it without changing the key or server.
        if [ ! -f "$task_public_key" ] && [ -f "$task_workspace/state/device-adb/adbkey" ] && command -v adb >/dev/null 2>&1; then
            task_public_temp=$task_workspace/state/device-adb/adbkey.pub.pending.$$
            if adb pubkey "$task_workspace/state/device-adb/adbkey" > "$task_public_temp" 2>/dev/null; then
                mv "$task_public_temp" "$task_public_key"
            else
                rm -f "$task_public_temp"
            fi
        fi
    fi
    case "$task_public_key" in *.pub) ;;
        *) printf '%s\n' 'The ADB public key path must end in .pub.' >&2; return 1;;
    esac
    if [ -f "$task_public_key" ]; then
        cp "$task_public_key" "$task_workspace/state/device-adb/active-adbkey.pub"
        chmod 600 "$task_workspace/state/device-adb/active-adbkey.pub"
        if [ "$task_backend" = host ]; then
            # Retain the Android host-server identity when switching to USB TWRP.
            cp "$task_public_key" "$task_workspace/state/device-adb/host-adbkey.pub"
            chmod 600 "$task_workspace/state/device-adb/host-adbkey.pub"
        fi
    else
        rm -f "$task_workspace/state/device-adb/active-adbkey.pub"
        printf '%s\n' 'Public key export unavailable. For a custom host key, set TAB_S3_HOST_ADB_PUBLIC_KEY; an older USB-mode client may need a recent host adb pubkey command.' >&2
    fi
}
case "$task_action" in
    image)
        exec podman build --pull=never --network=host -t "$task_image" \
            -f "$task_workspace/container/DeviceTools.Containerfile" "$task_workspace"
        ;;
    start)
        umask 077
        mkdir -p "$task_workspace/state/device-adb" "$task_workspace/backups" "$task_workspace/diagnostics"
        if podman container exists "$task_container"; then
            task_container_image=$(podman inspect --format '{{.Image}}' "$task_container")
            task_current_image=$(podman image inspect --format '{{.Id}}' "$task_image")
            if [ "$task_container_image" != "$task_current_image" ]; then
                podman rm --force "$task_container" >/dev/null
                printf '%s\n' 'Recreated device tools container for the current image.'
            fi
        fi
        if [ "$task_backend" = host ]; then
            command -v adb >/dev/null 2>&1 || {
                printf '%s\n' 'Host mode requires adb on PATH; use TAB_S3_ADB_BACKEND=usb for container USB access.' >&2
                exit 1
            }
            adb start-server
            if podman container exists "$task_container"; then
                task_existing=$(podman inspect --format '{{range .Mounts}}{{if eq .Destination "/workspace"}}{{.Source}}{{end}}{{end}}' "$task_container")
                [ "$task_existing" = "$task_workspace" ] || {
                    printf '%s\n' 'This device tools container belongs to another workspace.' >&2
                    exit 1
                }
                task_previous_backend=$(podman inspect --format '{{index .Config.Labels "io.tabs3.adb.backend"}}' "$task_container")
                if [ "$task_previous_backend" = host ] && [ "$(podman inspect --format '{{.State.Running}}' "$task_container")" = true ]; then
                    task_save_public_key
                    exec podman exec "$task_container" adb devices -l
                fi
                podman rm --force "$task_container" >/dev/null
            fi
            podman run --detach --name "$task_container" --pull=never --init \
                --network=host --userns=keep-id --user "$(id -u):$(id -g)" \
                --cpus=2 --memory=1g --cap-drop=ALL --security-opt=no-new-privileges \
                --label io.tabs3.adb.backend=host \
                --env ADB_SERVER_SOCKET=tcp:127.0.0.1:5037 \
                --env PYTHONDONTWRITEBYTECODE=1 \
                --volume "$task_workspace:/workspace" --workdir /workspace \
                "$task_image" sleep infinity >/dev/null
            task_save_public_key
            printf '%s\n' 'Using the host ADB server at 127.0.0.1:5037.'
            exec podman exec "$task_container" adb devices -l
        fi
        task_usb=${TAB_S3_USB_DEVICE:-}
        if [ -z "$task_usb" ]; then
            task_count=0
            for task_vendor_file in /sys/bus/usb/devices/*/idVendor; do
                [ -f "$task_vendor_file" ] || continue
                read -r task_vendor < "$task_vendor_file"
                case "$task_vendor" in 04e8|18d1) ;; *) continue;; esac
                task_sys=${task_vendor_file%/idVendor}
                read -r task_bus < "$task_sys/busnum"
                read -r task_address < "$task_sys/devnum"
                task_usb=$(printf '/dev/bus/usb/%03d/%03d' "$task_bus" "$task_address")
                task_count=$((task_count + 1))
            done
            [ "$task_count" = 1 ] || {
                printf '%s\n' 'Connect one Samsung/Android USB device, or set TAB_S3_USB_DEVICE to its /dev/bus/usb node.' >&2
                exit 1
            }
        fi
        case "$task_usb" in /dev/bus/usb/[0-9][0-9][0-9]/[0-9][0-9][0-9]) ;;
            *) printf '%s\n' 'Unexpected USB node path.' >&2; exit 1;; esac
        [ -c "$task_usb" ] || { printf '%s\n' 'USB device node is missing.' >&2; exit 1; }
        if podman container exists "$task_container"; then
            task_existing=$(podman inspect --format '{{range .Mounts}}{{if eq .Destination "/workspace"}}{{.Source}}{{end}}{{end}}' "$task_container")
            [ "$task_existing" = "$task_workspace" ] || {
                printf '%s\n' 'This device tools container belongs to another workspace.' >&2
                exit 1
            }
            # Rootless Podman may not expose --device in HostConfig.Devices.
            task_previous=$(podman inspect --format '{{index .Config.Labels "io.tabs3.usb.node"}}' "$task_container")
            task_previous_backend=$(podman inspect --format '{{index .Config.Labels "io.tabs3.adb.backend"}}' "$task_container")
            if [ "$task_previous_backend" = usb ] && [ "$task_previous" = "$task_usb" ] && [ "$(podman inspect --format '{{.State.Running}}' "$task_container")" = true ]; then
                task_save_public_key
                exec podman exec "$task_container" adb devices -l
            fi
            podman rm --force "$task_container" >/dev/null
        fi
        podman run --detach --name "$task_container" --pull=never --init \
            --network=none --userns=keep-id --user "$(id -u):$(id -g)" --group-add=keep-groups \
            --cpus=2 --memory=1g --cap-drop=ALL --security-opt=no-new-privileges \
            --label io.tabs3.adb.backend=usb --label "io.tabs3.usb.node=$task_usb" \
            --env PYTHONDONTWRITEBYTECODE=1 \
            --device "$task_usb:$task_usb:rw" \
            --volume "$task_workspace/state/device-adb:/workspace/.android" \
            --volume "$task_workspace:/workspace" --workdir /workspace "$task_image" >/dev/null
        podman exec "$task_container" adb devices -l
        task_save_public_key
        ;;
    stop)
        task_existing=$(podman inspect --format '{{range .Mounts}}{{if eq .Destination "/workspace"}}{{.Source}}{{end}}{{end}}' "$task_container")
        [ "$task_existing" = "$task_workspace" ] || exit 1
        exec podman rm --force "$task_container"
        ;;
    devices)
        exec podman exec "$task_container" adb devices -l
        ;;
    adb)
        exec podman exec "$task_container" adb "$@"
        ;;
    exec)
        exec podman exec "$task_container" "$@"
        ;;
    *) printf '%s\n' 'Usage: sh scripts/device.sh {image|start|stop|devices|adb ARGS...|exec COMMAND...}' >&2; exit 2;;
esac

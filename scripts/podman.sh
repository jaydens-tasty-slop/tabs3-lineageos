#!/bin/sh
# The host needs Podman and a normal POSIX shell. Build tools stay in the image.
set -eu
task_workspace=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
task_image=localhost/lineageos-gts3-build:ubuntu22.04
task_smoke_image=localhost/lineageos-gts3-media:ubuntu22.04
task_container=${TAB_S3_BUILD_CONTAINER:-lineageos-gts3-rom-build}
task_build_memory=${TAB_S3_BUILD_MEMORY:-38g}
task_build_memory_swap=${TAB_S3_BUILD_MEMORY_SWAP:-48g}
task_build_pids_limit=${TAB_S3_BUILD_PIDS_LIMIT:-8192}
task_action=${1:-status}
if [ "$#" -gt 0 ]; then shift; fi

task_shared_source() {
    case "$1" in
        android) printf '%s\n' "${TAB_S3_ANDROID_DIR:-$task_workspace/android}" ;;
        upstream) printf '%s\n' "${TAB_S3_UPSTREAM_DIR:-$task_workspace/upstream}" ;;
        state/ccache) printf '%s\n' "${TAB_S3_CCACHE_DIR:-$task_workspace/state/ccache}" ;;
    esac
}

# External directories get explicit child mounts. The mount points in this
# workspace must be real directories: OCI runtimes cannot mount through an
# outward-pointing symlink beneath the parent workspace bind mount.
task_podman_run() {
    for task_relative in android upstream state/ccache; do
        task_source=$(task_shared_source "$task_relative")
        task_destination=$task_workspace/$task_relative
        [ "$task_source" != "$task_destination" ] || continue
        [ -d "$task_source" ] || {
            printf 'Shared directory is missing: %s\n' "$task_source" >&2
            exit 1
        }
        if [ -L "$task_destination" ]; then
            printf 'Replace the local symlink with an empty directory before sharing: %s\n' "$task_destination" >&2
            exit 1
        fi
        mkdir -p "$task_destination"
        task_source=$(CDPATH= cd -- "$task_source" && pwd -P)
        task_label=$(printf '%s' "$task_relative" | tr / .)
        set -- --volume "$task_source:/workspace/$task_relative" \
            --label "io.tabs3.shared.$task_label=$task_source" "$@"
    done
    exec podman run "$@"
}

task_check_shared_mounts() {
    for task_relative in android upstream state/ccache; do
        task_source=$(task_shared_source "$task_relative")
        task_expected=
        if [ "$task_source" != "$task_workspace/$task_relative" ]; then
            task_expected=$(CDPATH= cd -- "$task_source" && pwd -P)
        fi
        task_label=$(printf '%s' "$task_relative" | tr / .)
        task_actual=$(podman inspect --format "{{index .Config.Labels \"io.tabs3.shared.$task_label\"}}" "$task_container")
        if [ "$task_actual" = '<no value>' ]; then task_actual=; fi
        [ "$task_actual" = "$task_expected" ] || {
            printf 'Container %s uses different shared directories. Choose another container name or remove the stopped container first.\n' "$task_container" >&2
            exit 1
        }
    done
}

case "$task_action" in
    image)
        exec podman build --pull=missing -t "$task_image" \
            -f "$task_workspace/container/Containerfile" "$task_workspace"
        ;;
    ensure-image)
        if podman image exists "$task_image"; then
            printf '%s\n' "Build image already exists: $task_image"
        else
            exec podman build --pull=missing -t "$task_image" \
                -f "$task_workspace/container/Containerfile" "$task_workspace"
        fi
        ;;
    status)
        exec podman ps -a --filter name=lineageos-gts3 --format '{{.Names}} {{.Status}}'
        ;;
    logs)
        exec podman logs --follow --tail=30 "$task_container"
        ;;
    build|package)
        task_build_script=scripts/build_rom.sh
        if [ "$task_action" = package ]; then
            task_container=${TAB_S3_PACKAGE_CONTAINER:-lineageos-gts3-rom-package}
            task_build_script=scripts/package_rom.sh
        fi
        if podman container exists "$task_container"; then
            task_existing_workspace=$(podman inspect --format '{{range .Mounts}}{{if eq .Destination "/workspace"}}{{.Source}}{{end}}{{end}}' "$task_container")
            if [ "$task_existing_workspace" != "$task_workspace" ]; then
                printf '%s\n' "Container $task_container belongs to another workspace. Set TAB_S3_BUILD_CONTAINER to a different name." >&2
                exit 1
            fi
            task_check_shared_mounts
            if [ "$(podman inspect --format '{{.State.Running}}' "$task_container")" = true ]; then
                exec podman logs --follow --tail=30 "$task_container"
            fi
            exec podman start --attach "$task_container"
        fi
        mkdir -p "$task_workspace/logs" "$task_workspace/state"
        task_podman_run --name "$task_container" --pull=never --init --network=none \
            --userns=keep-id --user "$(id -u):$(id -g)" \
            --cpus=24 --memory="$task_build_memory" --memory-swap="$task_build_memory_swap" \
            --pids-limit="$task_build_pids_limit" \
            --security-opt=no-new-privileges --cap-drop=ALL \
            --env PYTHONDONTWRITEBYTECODE=1 \
            --volume "$task_workspace:/workspace" --workdir /workspace \
            "$task_image" bash -c \
            'set -o pipefail; bash "$1" 2>&1 | tee logs/build-rom.log; result=${PIPESTATUS[0]}; printf "%s\n" "$result" > state/build-rom.exit; exit "$result"' \
            bash "$task_build_script"
        ;;
    exec)
        task_podman_run --rm --pull=never --network=none \
            --userns=keep-id --user "$(id -u):$(id -g)" \
            --security-opt=no-new-privileges --cap-drop=ALL \
            --env PYTHONDONTWRITEBYTECODE=1 \
            --volume "$task_workspace:/workspace" --workdir /workspace "$task_image" "$@"
        ;;
    smoke-payloads|qualification-payloads|browser-payloads)
        mkdir -p "$task_workspace/state" "$task_workspace/artifacts"
        task_payload_command='bash /workspace/scripts/build_smoke_payloads.sh'
        task_payload_network=none
        if [ "$task_action" = qualification-payloads ]; then
            task_payload_command='python3 /workspace/scripts/build_qualification_payloads.py'
        elif [ "$task_action" = browser-payloads ]; then
            task_payload_command='python3 /workspace/scripts/build_browser_payloads.py'
            task_payload_network=host
        fi
        task_podman_run --rm --pull=never --network="$task_payload_network" \
            --userns=keep-id --user "$(id -u):$(id -g)" \
            --cpus=4 --memory=6g --memory-swap=8g \
            --security-opt=no-new-privileges --cap-drop=ALL \
            --env PYTHONDONTWRITEBYTECODE=1 \
            --volume "$task_workspace:/workspace" --workdir /workspace \
            "$task_smoke_image" sh -c "$task_payload_command"
        ;;
    shell)
        set --
        if [ -t 0 ] && [ -t 1 ]; then
            set -- --interactive --tty
        fi
        task_podman_run --rm "$@" --pull=never --network=none \
            --userns=keep-id --user "$(id -u):$(id -g)" \
            --security-opt=no-new-privileges --cap-drop=ALL \
            --env PYTHONDONTWRITEBYTECODE=1 \
            --volume "$task_workspace:/workspace" --workdir /workspace \
            "$task_image" bash
        ;;
    fetch)
        task_podman_run --rm --pull=never --network=host \
            --userns=keep-id --user "$(id -u):$(id -g)" \
            --security-opt=no-new-privileges --cap-drop=ALL \
            --env PYTHONDONTWRITEBYTECODE=1 \
            --env TAB_S3_GIT_NAME --env TAB_S3_GIT_EMAIL \
            --volume "$task_workspace:/workspace" --workdir /workspace "$task_image" "$@"
        ;;
    *)
        printf '%s\n' 'Usage: sh scripts/podman.sh {image|ensure-image|status|logs|build|package|shell|exec COMMAND...|smoke-payloads|qualification-payloads|browser-payloads|fetch COMMAND...}' >&2
        exit 2
        ;;
esac

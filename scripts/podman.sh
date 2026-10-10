#!/bin/sh
# The host needs Podman and a normal POSIX shell. Build tools stay in the image.
set -eu
task_workspace=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
task_image=localhost/lineageos-gts3-build:ubuntu22.04
task_smoke_image=localhost/lineageos-gts3-media:ubuntu22.04
task_container=${TAB_S3_BUILD_CONTAINER:-lineageos-gts3-rom-build}
task_action=${1:-status}
if [ "$#" -gt 0 ]; then shift; fi

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
            if [ "$(podman inspect --format '{{.State.Running}}' "$task_container")" = true ]; then
                exec podman logs --follow --tail=30 "$task_container"
            fi
            exec podman start --attach "$task_container"
        fi
        mkdir -p "$task_workspace/logs" "$task_workspace/state"
        exec podman run --name "$task_container" --pull=never --init --network=none \
            --userns=keep-id --user "$(id -u):$(id -g)" \
            --cpus=24 --memory=38g --memory-swap=48g \
            --security-opt=no-new-privileges --cap-drop=ALL \
            --env PYTHONDONTWRITEBYTECODE=1 \
            --volume "$task_workspace:/workspace" --workdir /workspace \
            "$task_image" bash -c \
            'set -o pipefail; bash "$1" 2>&1 | tee logs/build-rom.log; result=${PIPESTATUS[0]}; printf "%s\n" "$result" > state/build-rom.exit; exit "$result"' \
            bash "$task_build_script"
        ;;
    exec)
        exec podman run --rm --pull=never --network=none \
            --userns=keep-id --user "$(id -u):$(id -g)" \
            --security-opt=no-new-privileges --cap-drop=ALL \
            --env PYTHONDONTWRITEBYTECODE=1 \
            --volume "$task_workspace:/workspace" --workdir /workspace "$task_image" "$@"
        ;;
    smoke-payloads)
        mkdir -p "$task_workspace/state" "$task_workspace/artifacts"
        exec podman run --rm --pull=never --network=none \
            --userns=keep-id --user "$(id -u):$(id -g)" \
            --cpus=4 --memory=6g --memory-swap=8g \
            --security-opt=no-new-privileges --cap-drop=ALL \
            --env PYTHONDONTWRITEBYTECODE=1 \
            --volume "$task_workspace:/workspace" --workdir /workspace \
            "$task_smoke_image" bash /workspace/scripts/build_smoke_payloads.sh
        ;;
    shell)
        set --
        if [ -t 0 ] && [ -t 1 ]; then
            set -- --interactive --tty
        fi
        exec podman run --rm "$@" --pull=never --network=none \
            --userns=keep-id --user "$(id -u):$(id -g)" \
            --security-opt=no-new-privileges --cap-drop=ALL \
            --env PYTHONDONTWRITEBYTECODE=1 \
            --volume "$task_workspace:/workspace" --workdir /workspace \
            "$task_image" bash
        ;;
    fetch)
        exec podman run --rm --pull=never --network=host \
            --userns=keep-id --user "$(id -u):$(id -g)" \
            --security-opt=no-new-privileges --cap-drop=ALL \
            --env PYTHONDONTWRITEBYTECODE=1 \
            --env TAB_S3_GIT_NAME --env TAB_S3_GIT_EMAIL \
            --volume "$task_workspace:/workspace" --workdir /workspace "$task_image" "$@"
        ;;
    *)
        printf '%s\n' 'Usage: sh scripts/podman.sh {image|ensure-image|status|logs|build|package|shell|exec COMMAND...|smoke-payloads|fetch COMMAND...}' >&2
        exit 2
        ;;
esac

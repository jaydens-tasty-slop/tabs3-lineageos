#!/usr/bin/env bash
# Called only by the opt-in, network-disabled media tools Podman image.
set -euo pipefail
cd /workspace
exec python3 /workspace/scripts/build_smoke_payloads.py

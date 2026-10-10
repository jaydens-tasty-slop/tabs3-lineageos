.DEFAULT_GOAL := build
-include local.mk
TAB_S3_ANDROID_DIR ?= $(CURDIR)/android
export TAB_S3_ANDROID_DIR TAB_S3_UPSTREAM_DIR TAB_S3_CCACHE_DIR
.PHONY: help image setup build package status logs shell source-check smoke smoke-payloads smoke-hardware \
	device-image device-start devices ensure-image ensure-sources ensure-device-image ensure-smoke-image \
	sleep-study-payload sleep-study-start sleep-study-finish
.NOTPARALLEL:
export SERIAL
TAB_S3_SLEEP_HOURS ?= 12

help:
	@printf '%s\n' \
	  'Targets:' \
	  '  make              Set up a fresh checkout if needed and build the ROM' \
	  '  make image        Build the Android build image' \
	  '  make setup        Fetch upstream sources and apply the pinned port' \
	  '  make build        Build the ROM using the persistent workspace' \
	  '  make package      Package from the existing build output' \
	  '  make status       Show Tab S3 build containers' \
	  '  make logs         Follow the current build logs' \
	  '  make shell        Open a shell in the build image' \
	  '  make source-check Verify the pinned source patch snapshot' \
	  '  make device-image Build the optional ADB tools image' \
	  '  make device-start Start the ADB tools container' \
	  '  make devices      Start ADB tools and list connected devices' \
	  '  make smoke        Run read-only basic SM-T820 platform checks' \
	  '  make smoke-payloads Generate local media/GPU smoke payloads in Podman' \
	  '  make smoke-hardware Run opt-in unlocked app-level media/GPU/audio/WebView smoke' \
	  '  make sleep-study-start  Start a private unplugged sleep study' \
	  '  make sleep-study-finish Collect and analyze the active sleep study'

ensure-image:
	sh scripts/podman.sh ensure-image

image:
	sh scripts/podman.sh image

setup: ensure-image
	sh scripts/podman.sh fetch bash scripts/setup_checkout.sh

ensure-sources: ensure-image
	@if [ -d "$(TAB_S3_ANDROID_DIR)/.repo" ]; then \
	  if [ ! -f "$(TAB_S3_ANDROID_DIR)/build/envsetup.sh" ]; then \
	    printf '%s\n' 'Android checkout is incomplete. Resume source sync as described in docs/BUILDING.md.' >&2; \
	    exit 1; \
	  fi; \
	  printf '%s\n' 'Reusing the existing Android checkout and build output.'; \
	else \
	  sh scripts/podman.sh fetch bash scripts/setup_checkout.sh; \
	fi

build: ensure-sources
	sh scripts/podman.sh build

package: ensure-image
	sh scripts/podman.sh package

status:
	sh scripts/podman.sh status

logs:
	sh scripts/podman.sh logs

shell: ensure-image
	sh scripts/podman.sh shell

source-check: ensure-image
	sh scripts/podman.sh exec python3 scripts/verify_source_export.py

device-image: ensure-image
	sh scripts/device.sh image

ensure-device-image:
	@if podman image exists localhost/lineageos-gts3-device:ubuntu22.04; then \
	  printf '%s\n' 'Device tools image already exists'; \
	else \
	  sh scripts/podman.sh ensure-image && sh scripts/device.sh image; \
	fi

device-start: ensure-device-image
	sh scripts/device.sh start

devices: device-start

smoke: device-start
	sh scripts/device_smoke.sh

ensure-smoke-image: ensure-device-image
	@if podman image exists localhost/lineageos-gts3-media:ubuntu22.04; then \
	  printf '%s\n' 'Smoke payload image already exists'; \
	else \
	  podman build --pull=never --network=host -t localhost/lineageos-gts3-media:ubuntu22.04 \
	    -f container/MediaTools.Containerfile .; \
	fi

smoke-payloads: ensure-smoke-image
	sh scripts/podman.sh smoke-payloads

smoke-hardware: smoke-payloads device-start
	sh scripts/device_smoke_hardware.sh

sleep-study-payload: ensure-image
	sh scripts/podman.sh exec python3 scripts/build_sleep_clock.py

sleep-study-start: sleep-study-payload device-start
	@task_serial=$${SERIAL:-}; \
	if [ -z "$$task_serial" ]; then \
	  task_serials=$$(sh scripts/device.sh adb devices | awk 'NR > 1 && $$2 == "device" { print $$1 }'); \
	  set -- $$task_serials; \
	  if [ "$$#" -ne 1 ]; then \
	    printf '%s\n' 'Connect exactly one authorized device or select one with SERIAL=<adb-serial>.' >&2; \
	    exit 2; \
	  fi; \
	  task_serial=$$1; \
	fi; \
	sh scripts/device.sh exec python3 scripts/device_sleep_study.py start \
	  --serial "$$task_serial" --hours "$(TAB_S3_SLEEP_HOURS)" \
	  --clock-helper artifacts/device-sleep-clock/sleep-clock

sleep-study-finish: device-start
	sh scripts/device.sh exec python3 scripts/device_sleep_study.py finish

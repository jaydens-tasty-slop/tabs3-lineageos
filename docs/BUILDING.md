# Build and reconstruct the workspace

## Host requirements

Use Make, a POSIX shell and rootless Podman on Linux. Host `adb` is optional;
without it, the device tools image can access one USB-connected tablet. Keep the
source checkout and build output on a filesystem that supports Unix ownership,
permissions, symlinks and hard links. A removable NTFS/exFAT disk is useful for
backups or finished ZIPs, rather than the Android checkout.

The supplied build profile allows 24 CPU cores, 38 GiB memory and up to 48 GiB
including swap. A host with 64 GiB RAM and several hundred GiB of free storage is
a practical starting point. These are the working profile, not measured minimum
requirements. Fetches require Internet access; compilation runs without network.

## Fresh checkout

Clone the build-root repository into an empty workspace. From that directory:

```sh
make help
make image
make setup
make build
```

`setup_checkout.sh` clones the requested device repositories, initializes Android
`repo` at the pinned Lineage manifest, synchronizes the 1,174 revisions in
`manifests/base-source-lock.xml`, and applies every patch in `patches/index.json`.
It refuses to replace an existing Android checkout. Patch checksums and base
revisions are verified before application. Keep the pinned manifest and patch
index together; arbitrary upstream updates require reviewing the port again.

On hosts enforcing SELinux, the workspace bind mount may need an appropriate
container label. Apply your host's normal Podman volume-labeling policy to this
workspace; the build commands do not disable host SELinux.

## Layout

| Path | Purpose | In build-root Git? |
| --- | --- | --- |
| `Makefile` | Common host entry points | Yes |
| `container/` | Build and optional ADB tools image definitions | Yes |
| `manifests/` | Pinned Android projects and vendor exceptions | Yes |
| `patches/` | Complete port delta and checksums | Yes |
| `scripts/` | Selected portable build/source and read-only device smoke tools | Selected files |
| `docs/` | Build, source and qualification notes | Yes |
| `android/` | Android `repo` checkout, including device/kernel/vendor projects | No |
| `android/out/` | Persistent build graph, intermediates and product output | No |
| `upstream/` | Original Git clones, including `repo` | No |
| `state/ccache/` | Persistent compiler cache, capped at 30 GiB | No |
| `logs/`, `artifacts/` | Local logs and distribution artifacts | No |
| `backups/`, `diagnostics/`, `research/` | Private device evidence and working notes | No |

No submodules are needed. Android's `repo` owns the large source checkout; the
small outer repository owns the manifest, port patches and build instructions.
The four device/kernel/vendor convenience forks preserve upstream ancestry and
the R8 repairs. The common-device branch also includes the later source cleanup
that removes the temporary forced-ADB rule. The 26-project patch snapshot and
1,174 pinned base revisions are canonical; see [the source map](SOURCES.md).

The build uses the standard Lineage version ID from `ro.lineage.version`: UTC
date, with the upstream optional time-of-day suffix enabled by default. The
current signed candidate is `23.2-20261010_003605-UNOFFICIAL-gts3lwifi`. Its
offline signing/image audits and same-key TWRP dirty upgrade passed, preserving
separate GApps. The exact ZIP booted and passed bounded secure ordinary-ADB,
core-process, bitmap, Settings/Wellbeing UI and offline TTS checks. The previous
`140353` candidate passed a clean installation; the new ZIP's clean-install
path and unplugged study remain pending. Earlier R8 runtime results apply to
the named earlier package. Settings Build number uses Android's platform build
ID, while the LineageOS version includes the date.

The build and package targets pass the established legacy kernel host-tool
flags through `TARGET_KERNEL_ADDITIONAL_FLAGS`: Ubuntu GCC/G++, binutils,
GNU89 host C, an eight-job kernel limit, and stable builder/host names. Override
`TAB_S3_KERNEL_MAKE_FLAGS` to review a different kernel tool profile. These are
the flags used for the signed candidate; a second fresh build has not been run
to qualify reconstruction. No cache clean is needed for ordinary iterations.

The ordinary targets produce development-signed output. See [signing](SIGNING.md)
for the additional target-files, package/APEX and OTA signing steps before
public distribution. Private keys remain local and are reused across updates.

## Offline release gate

Both `make build` and `make package` finish with the same release gate after
`otapackage` and the required host image tools are available. The gate checks
source configuration, the unpacked target-files System tree, the System image,
Boot image and full OTA ZIP. It rejects the temporary device-specific forced
USB ADB rule, embedded ADB authorization keys and insecure ADB settings. It
also verifies Boot against the OTA, confirms every System transfer range
matches the built System image, and matches the packaged Lineage version,
incremental and UTC timestamp to the OTA metadata.

Hashes for the patch index, target-files tree, System image, Boot image and OTA
are recorded before and after the check. A unique private report is written
under ignored `state/release-adb-audit.*`. Only after the audit passes does the
finalizer refresh `system.img` and create the standard
`lineage-<ro.lineage.version>.zip` alias and checksum. This is a package/source
integrity check; it does not install or boot Android. The signed candidate has not yet completed Android boot checks; earlier R8
runtime results do not transfer.

The audit imports `scripts/verify_system_payload.py` and `scripts/verify_ota.py`;
all three audit scripts are included in the curated source root. It reads
`debugfs_static`, `simg2img` and the repository-pinned Brotli decoder from the
Android build tools. It does not mount the System image.

## Basic device smoke check

Build the optional ADB tools image and start its container once:

```sh
make device-image
make device-start
make devices
make smoke
```

Host `adb` is used when it is installed. Otherwise, `device-start` uses the
rootless Podman USB path and requires access to the connected USB device. To
select a specific authorized device when more than one is visible, use
`make smoke SERIAL=<adb-serial>`.

The smoke check is read-only on the tablet. It checks SM-T820/gts3lwifi identity,
Android 16 boot completion, core system services, runtime and ART APEX mounts,
the system package inventory and the last 200 crash-buffer log entries. It
refuses ambiguous device selection when `SERIAL` is omitted. Crash log text is
neither printed nor saved. It does not install an app or test payload, reboot,
flash or reset the device. Camera, media and graphics probes remain outside
this portable smoke suite.

## Opt-in hardware smoke

After `make build`, create or validate the local smoke payloads and run the
bounded app-level checks with:

```sh
make smoke-payloads
make smoke-hardware SERIAL=<adb-serial>
```

`smoke-payloads` reuses the existing Android checkout, SDK and compiler output
inside Podman. It builds only the permission-free media probe APK, synthetic
AVC/HEVC/AAC fixtures, and a Vulkan compute diagnostic. The Vulkan binary links
to the current Android build's `libvulkan` and Bionic outputs, so this target
does not replace the initial Android build. Payload generation runs without
container network access; creating its optional FFmpeg tools image can fetch
the Ubuntu packages on first use. Generated APKs, binaries, fixtures and the
local signing key stay in ignored `artifacts/` and `state/`. Existing payloads
are hash-checked and reused; stale output is left in place and reported instead
of being overwritten.
The generated keystore uses a documented throwaway password for this local
diagnostic APK only; it is never used for ROM or release signing.

`smoke-hardware` uses the ADB tools container and requires Android 16, completed
first-run setup, USB power and a normal user unlock. It checks a short AVC, HEVC
and AAC decode, GLES rendering, a generated AudioTrack route, a local
WebView page, and Vulkan compute. It does not require root ADB, host FFmpeg,
accounts or public network access.
The coordinator temporarily enables USB stay-awake and restores its exact
previous setting. Probe APKs are removed only when that run installed them;
each run stages and removes only its uniquely named generated files. Private
reports remain under ignored `diagnostics/`.

These short checks establish that the selected paths return expected results;
they do not qualify long playback, DSP offload, audible speaker quality, DRM,
Vulkan presentation, WebView internet access, performance or endurance. The
existing `make smoke` remains the basic read-only platform check.

## Unplugged sleep and Wi-Fi observation

After foreground tests and any USB stay-awake keeper have stopped, confirm the
keeper report says it is inactive and restored its original value of `0`. If
a keeper is still active, write the exact `stop\n` marker to the marker path it
printed, then wait for its final report to confirm restoration. Do not kill
the keeper process or change the setting by hand. The sleep-study collector
refuses to start unless USB stay-awake is `0` or unset and wireless ADB is
disabled.

Start an approximately twelve-hour study with:

```sh
make sleep-study-start
```

To select one tablet when more than one authorized device is connected, or to
choose another duration from 1 to 48 hours, use:

```sh
make sleep-study-start SERIAL=<adb-serial> TAB_S3_SLEEP_HOURS=12
```

`SERIAL` is optional when exactly one authorized tablet is connected. The
target starts the existing ADB tools container and runs
`scripts/device_sleep_study.py`; it does not build the ROM. Wait for “Study
ready”, unplug USB, turn the screen off normally, and leave the tablet unused
on its usual saved Wi-Fi and normal physical setup for the selected interval.
Keep wireless ADB off. Do not poll the tablet, connect USB, charge, reboot,
toggle Wi-Fi, or change its saved network during the interval. No host process
needs to remain running.

Reconnect USB and collect the finish snapshot before using the tablet:

```sh
make sleep-study-finish
```

The collector prints USB/ADB readiness and progress for each probe. If the
tablet is absent or unauthorized, reconnect USB and accept its normal debugging
prompt if needed, then retry after checking `make devices`. Individual probes
have timeouts; a repeated finish keeps the existing completed evidence.

The start and finish snapshots preserve Android battery history and capture
battery, power, Wi-Fi, connectivity, GApps packages/jobs, memory, suspend, RPM,
wakeup-source and boot/core identity data. Unreadable counters are marked
unavailable. The collector uses the incoming ADB identity and never requests
root. A tiny arm64 clock payload reads CLOCK_BOOTTIME and CLOCK_MONOTONIC once
at each endpoint; it is staged in a unique temporary directory and removed
before capture completes. Their difference measures kernel suspend time even
when `/proc/timer_list` is inaccessible to ordinary ADB. `make` builds this
payload in Podman from existing Android compiler/libc outputs, without starting
a ROM build. It does not run an on-device logger during the unplugged interval.
The active study path is
stored in ignored `state/active-sleep-study.json`; reports remain under ignored
`diagnostics/`.

Treat the raw reports as private: Wi-Fi status and battery history can contain
local network identifiers, and snapshots contain the device serial. Keep raw
copies only in owner-controlled private storage; do not commit or publish them.
The generated analysis requires a separate review of battery history for the
real unplugged interval, charging and screen events, plus Wi-Fi connection and
disconnection events. It does not automatically replace raw endpoint battery
readings with precharge readings. If USB recharging precedes capture, inspect
the history before reporting drain; a full battery at the endpoint does not
mean standby used no energy. Charged aggregate statistics can reset after
recharging while the retained event history remains useful.
Endpoint clocks include the brief USB observations, battery percentages are
coarse, and suspend counters do not prove the deepest Qualcomm power state.

The earlier R4 overnight observation was on a different build and had a Wi-Fi
disconnect whose cause was not determined. R8's separate kernel #15 scheduled
scan and short screen-off rejoin checks do not establish overnight behavior.
The current signed `003605` ZIP and #17 kernel have a reviewed 11h48m unplugged
overnight observation with separate GApps: battery 100% to 98%, unchanged
boot/core identities, and one brief Wi-Fi disconnect that recovered with the
screen off in about one second. The earlier multi-hour outage was not
reproduced. This qualifies that one observation; it does not show that PNO
caused or fixed the older disconnect or transfer qualification to R8's #15
kernel. Keep a sanitized summary separate from frozen build provenance;
retain raw evidence privately.

## Incremental work

```sh
make build
make logs
make status
```

The whole workspace is bound at the stable container path `/workspace`.
`OUT_DIR=out` therefore stays in `android/out`, and `CCACHE_DIR` stays in
`state/ccache`. Output and caches survive container exit or replacement. Reusing
the checkout also preserves Ninja's build graph and timestamps.

The wrapper restarts the existing named build container, or follows its logs
if already running. It refuses a container associated with another workspace.
After changing the image or wrapper resource profile, remove the stopped build
container and rerun the wrapper to pick up the new settings. Keep the workspace
and `state/ccache` to preserve incremental output.

To invoke a specific Android target, open a shell and load the build environment:

```sh
make shell
source /workspace/scripts/build_env.sh
m -j8 otapackage
```

`make package` also packages through the existing build graph. Neither command
guarantees a packaging-only operation if Ninja sees changed inputs. Avoid
`clean`, `clobber`, deleting `android/out` or changing container paths unless
the rebuild is intentional.

Product artifacts are under `android/out/target/product/gts3lwifi/`. The TWRP
installer is the generated `lineage-*.zip`; copy the selected release and its
checksum into a distribution directory. Do not confuse a kernel `boot.img` with
the complete ROM installer.

LineageOS names the public ZIP `lineage-23.2-YYYYMMDD-UNOFFICIAL-gts3lwifi.zip`
using the UTC build date. Its optional time-of-day setting adds
`_HHMMSS` to the version. Keep experiment labels such as R4 and R8 in release
notes and qualification records, not in the public ZIP basename.

## Source checks and maintenance

```sh
make source-check
```

This checks patch application/reversal against private Git indexes and compares
the result with the current checkout. It does not build, flash or reboot.

`export_port.py` can update the patch snapshot after deliberate source changes.
Run it in the build image with Git LFS configured, inspect the diff, update the
qualification notes, and audit the exported source before publication. A new
snapshot needs matching device tests and a new artifact checksum. The pinned
source snapshot does not pin every Ubuntu package or promise bit-identical ZIPs.

## Recovery and Google Apps

The tested installation path uses the maintainer's TWRP 3.7.0_9-0
without-encryption recovery build on the Wi-Fi SM-T820; encrypted Data is
unsupported. Back up device partitions and internal storage before changing an
installation. The ROM installer writes Boot and System;
it does not install Samsung firmware or replace recovery.

An Android-major-version upgrade needs a reviewed clean-install procedure. Do
not assume Android 14 Data can be retained. Google Apps, when used, must match
Android 16/ARM64 and be installed separately in recovery immediately after the
ROM, before its first Android boot. Installing Google Apps onto an already booted
installation requires a factory reset. A clean R4 install followed by the
separate MindTheGapps Android 16 ARM64 add-on has booted. The R8 dirty upgrade
retained the separate add-on and passed bounded package/runtime checks after
normal unlock. Account setup, Play Store certification/downloads, and broader
Google Apps behavior remain unqualified. Google Apps are not part of the ROM
ZIP. See [the installation guide](INSTALLING.md) for the tested R8 dirty-upgrade
scope and clean-install limits.

The R8 dirty-upgrade procedure is documented; a clean R8 installation is not
qualified. The development-signed ZIP remains an experimental maintainer build.

# LineageOS 23.2 for Samsung Galaxy Tab S3

Podman build instructions and the source changes for **Android 16 on SM-T820
(`gts3lwifi`)**. This is an unofficial experimental port, based on awesometic's
Tab S3 sources. SM-T825/LTE is not qualified.

The current tested build is **HARDWARE-R4**, dated October 7, 2026. It installs
through the maintainer's **TWRP 3.7.0 without encryption**. The kernel remains
**3.18.140**, with compatibility repairs required by this device's proprietary
hardware stack. A newer kernel port has not been qualified.

## Build

Clone this build-root repository into a directory on a Linux filesystem, then:

```sh
cd lineage-os
make help
make image
make setup
make build
```

The host needs Make, Podman and a POSIX shell; host `adb` is optional for device
checks. Android build dependencies are installed in the container. The setup,
build, package, shell and source-check targets build the image if it is missing.
See [the build guide](docs/BUILDING.md) for resource requirements, layout,
incremental builds, artifact locations, the read-only device smoke check and
optional media/GPU smoke targets.

The checkout is reconstructed with **Android `repo`, a pinned manifest and
versioned patches**. There are no Git submodules. The device, kernel and vendor
forks provide convenient source review; the complete patch snapshot also
reconstructs the port from its pinned upstream bases. All Android projects are
Git clones.

## Current qualification

The exact R4 ZIP booted on an SM-T820 and passed bounded camera, Wi-Fi, microphone,
sensor, GLES/Vulkan, WebView, hardware video decoder/encoder and DSP audio checks.
The owner verified Bluetooth pairing and wired headphones. These checks establish
specific operations, not complete application or daily-use reliability.

An unplugged overnight observation lasted about 12 hours 19 minutes: battery
100% to 98%, approximately 98.8% kernel suspend, no reboot. Wi-Fi was disconnected
for about 4 hours 53 minutes and rejoined when the screen woke. This result does
not establish continuously connected standby behavior.

**Open issues:** screen-off Wi-Fi reconnects, occasional app-switch stutter,
browser dropped frames, a clipped screen-lock setup heading, and remaining
camera quality/long-session checks. SELinux is permissive, Data encryption is
unsupported, Verified Boot is disabled, and the kernel/vendor components are
old. See [known issues and test scope](docs/KNOWN_ISSUES.md).

R4 currently uses development signing keys. A clean R4 install followed by the
separate MindTheGapps Android 16 ARM64 add-on has booted. Google Apps qualification
is in progress: Speech Services and Digital Wellbeing crashed before the first
user unlock and need follow-up checks. Release signing and qualification of the
final signed package remain pending. Google Apps are not included in the ROM
build. No public download or OTA service is configured by this repository.

## Source snapshot

- Base lock: `manifests/base-source-lock.xml`, 1,174 pinned projects.
- Port snapshot: `patches/index.json`, 23 changed projects and SHA-256 checksums.
- Source forks: [the source map](docs/SOURCES.md).
- Tested R4 ZIP SHA-256:
  `ad7115e2548aa765ca4e1373ad448aa8f273268df364b6c0e1aab538c1277cfa`.

Source application and reversal were checked against the tested source trees.
A full build from a second fresh checkout and byte-for-byte reproduction have
not been performed. Build dates, signing and distribution packaging may change
artifact hashes.

## Credits and licenses

Thanks to awesometic for the original device, kernel, vendor and recovery work;
to LineageOS, AOSP, Samsung, Qualcomm and the other upstream contributors.

[Original Tab S3 ROM thread](https://xdaforums.com/t/rom-unofficial-14-eas-ota-sm-t820-sm-t825-2024-3-9-lineageos-21-for-galaxy-tab-s3.4660924/).

Build-root orchestration and documentation are licensed under Apache-2.0.
Patched upstream code retains its own licenses. The kernel is GPLv2; vendor
binaries retain their existing distribution terms. See [NOTICE](NOTICE).

# LineageOS 23.2 for Samsung Galaxy Tab S3

Podman build instructions and source changes for Android 16 on SM-T820
(`gts3lwifi`). This is an unofficial experimental port based on awesometic's
Tab S3 sources. SM-T825/LTE is not qualified.

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
incremental builds, artifact locations, read-only device checks and optional
media/GPU smoke targets.

The checkout is reconstructed with Android `repo`, a pinned manifest and
versioned patches. There are no Git submodules. The device, kernel and vendor
forks provide convenient source review; the complete patch snapshot also
reconstructs the port from its pinned upstream bases. All Android projects are
Git clones.

## Qualification status

HARDWARE-R4 is the only ROM package documented as fully ZIP-boot-tested on
SM-T820. The documented recovery path is TWRP 3.7.0 without encryption, with
Recovery preserved. A later R4 Data/Cache reset and separate MindTheGapps
Android 16 ARM64 installation also booted. Google Apps follow-up remains
incomplete. The audio-route source update is an R5 candidate: its patch export
and targeted product-property/property-context build passed, and a temporary
runtime candidate preserved owner-confirmed ordinary website audio through two
headphone plug/unplug cycles. Full R5 package verification, installation and
boot remain pending. The R4 results do not qualify an R5 package.

The R4+GApps camera regression completed bounded Camera2 full-size JPEG,
Camera1 JPEG, AVC/HEVC video and embedded WebView camera checks so far. The
camera regression review is still in progress. Camera image quality, green-bar
behavior, long sessions and repeated cold boots remain open.

Chrome 154 passed a generated local-page JavaScript/WebGL fixture with Adreno
530 rendering, and generated AVC/HEVC 1080p60 clips passed coarse pixel checks.
The 20-second clips reported 125/1,200 dropped AVC frames and 39/1,200 dropped
HEVC frames. These counters do not establish smooth paced 60 fps playback or
identify the cause. A six-sample post-GApps memory capture reported about
1.33–1.72 GiB MemAvailable, with modest direct reclaim/allocation stalls late in
the sample. It did not establish severe sustained memory exhaustion or a cause
for frame jank.

An unplugged overnight R4 observation lasted about 12 hours 19 minutes:
battery 100% to 98%, approximately 98.8% kernel suspend, no reboot. Wi-Fi was
disconnected for about 4 hours 53 minutes and rejoined when the screen woke;
this does not establish continuously connected standby behavior.

## Open issues and inherited limits

Screen-off Wi-Fi reconnects, occasional app-switch stutter, browser dropped
frames, camera quality/endurance and the clipped Choose screen lock heading in
LineageOS onboarding remain open. The standard Settings lock picker was observed
without that clipping; the onboarding layout issue remains under review. See
[known issues and test scope](docs/KNOWN_ISSUES.md).

SELinux is permissive, Data encryption is unsupported, Verified Boot is
disabled, and the kernel/vendor components are old. The current R4 build uses
development signing keys. Release signing, clean installation of the final
signed package and repeated cold-boot checks remain pending. Google Apps,
Magisk and a public OTA channel are not qualified. Google Apps are not included
in the ROM build; no download or OTA service is configured here.

## Source snapshot

- Base lock: `manifests/base-source-lock.xml`, 1,174 pinned projects.
- Current port snapshot: `patches/index.json`, 24 changed projects and SHA-256
  checksums. The R5 candidate adds `system/sepolicy` and updates the Wi-Fi
  product and audio-policy patches; the source lock is unchanged.
- Source forks: [the source map](docs/SOURCES.md). The Wi-Fi branch includes
  the R5 source change, but no R5 ROM qualification is claimed.
- Historical tested R4 ZIP SHA-256:
  `ad7115e2548aa765ca4e1373ad448aa8f273268df364b6c0e1aab538c1277cfa`.

Source application and reversal passed round-trip checks for all 24 exported
projects. That establishes source reconstruction, not a full build or byte-for-
byte reproducibility. Build dates, signing and packaging may change artifact
hashes.

## Credits and licenses

Thanks to awesometic for the original device, kernel, vendor and recovery work;
to LineageOS, AOSP, Samsung, Qualcomm and the other upstream contributors.

[Original Tab S3 ROM thread](https://xdaforums.com/t/rom-unofficial-14-eas-ota-sm-t820-sm-t825-2024-3-9-lineageos-21-for-galaxy-tab-s3.4660924/).

Build-root orchestration and documentation are licensed under Apache-2.0.
Patched upstream code retains its own licenses. The kernel is GPLv2; vendor
binaries retain their existing distribution terms. See [NOTICE](NOTICE).

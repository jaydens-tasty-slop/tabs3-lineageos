# LineageOS 23.2 for Samsung Galaxy Tab S3

Podman build instructions and source changes for **Android 16 on SM-T820
(`gts3lwifi`)**. This is an unofficial experimental port based on awesometic's
Tab S3 sources. SM-T825/LTE is not qualified.

The only fully ZIP-boot-tested ROM is **HARDWARE-R4**, dated October 7, 2026.
It installs through the maintainer's **TWRP 3.7.0 without encryption**. The
experimental **HARDWARE-R8** package has passed offline source, image-delta,
module and Boot reviews. Its #15 kernel passed a fresh bounded Boot/PNO/rejoin
trial: the screen-off saved-network rejoin took 1.1 seconds, and twelve samples
over 60 seconds stayed connected while the display was off. This USB-polled
trial does not establish deep-sleep or overnight behavior. The full R8 ROM has
since been installed through a TWRP dirty upgrade, passed targeted read-only
post-install checks, and booted Android 16. Its first boot completed in about
121 seconds, followed by a 30-second stable monitor interval. These bounded
checks do not establish full application or accessory qualification.

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
See [the build guide](docs/BUILDING.md) for resources, layout, incremental
builds, artifact locations, the read-only device smoke check and optional
media/GPU smoke targets.

The checkout is reconstructed with **Android `repo`, a pinned manifest and
versioned patches**. There are no Git submodules. The device, kernel and vendor
forks provide convenient source review; the complete patch snapshot
reconstructs the port from pinned upstream bases. All Android projects are Git
clones.

## Current qualification

The exact R4 ZIP booted on an SM-T820 and passed bounded camera, Wi-Fi,
microphone, sensor, GLES/Vulkan, WebView, hardware video decoder/encoder and DSP
audio checks. Chrome 154 passed a generated local JavaScript/WebGL fixture using
Adreno 530. Separate generated 20-second 1080p60 clips reported 27 AVC and 6
HEVC dropped frames; these counters do not establish paced 60 fps. The owner
verified Bluetooth pairing and wired headphones. These results cover specific
operations, not complete application or daily-use reliability.

R8's targeted post-install verifier passed all 27 changed System content,
module, and metadata checks, plus exact checks of the three separate Google
core APKs and add-on script. The first Android 16 boot completed, and basic
boot/service/APEX/package/crash-buffer smoke checks passed. A synthetic input
event test exercised the Samsung cover-switch filter. The owner later reported
multiple cover reconnects and working Search in Chrome; Search was inert in the
launcher, and the language key had no visible effect. A read-only check
confirmed the selected System keylayout, but the reconnect capture was not
event-aligned and does not prove the physical behavior is fixed.

After normal unlock, bounded Google package/runtime checks passed, but account
setup, Play Store certification/downloads, and interactive behavior remain
unverified. The first foreground batch was inconclusive because of a staging
path mismatch and inventory/APK-install failures. A corrected bounded run then
passed GLES2/3 drawing, ES3.1 compute, WebView JavaScript, and a speaker-route
audio API check that confirmed sample acceptance, not human audibility. Five
generated decode fixtures passed individually. Inventory
found 16 of 21 expected vendor components, so the aggregate media suite remained
false because five legacy VC-1/DivX components are absent. Chrome 154 passed a
generated JavaScript/WebGL fixture on Adreno
530 and completed 20-second AVC/HEVC 1080p60 clips with expected pixel samples.
AVC reported 12 dropped of 1,200 frames and HEVC 8 of 1,200; the browser
reported 897 and 892 frame callbacks. These counters do not establish paced
60 fps or prove hardware decoding for every frame. Broader media and encoder
stress remain pending until a future normal screen unlock.

An unplugged overnight R4 observation lasted about 12 hours 19 minutes:
battery 100% to 98%, approximately 98.8% kernel suspend, no reboot. Wi-Fi was
disconnected for about 4 hours 53 minutes and rejoined when the screen woke.
This does not establish continuously connected standby behavior.

**Open issues:** deep-sleep and overnight Wi-Fi behavior, occasional app-switch
stutter, browser dropped frames, a clipped Lineage onboarding screen-lock
heading, and remaining camera quality/long-session checks. R8 includes a new
kernel #15 and audio/input changes. The first boot and bounded health checks
passed, but launcher Search, a controlled language-key change, owner-confirmed
post-upgrade audio, broader media/encoder stress, and application behavior
remain unqualified.
SELinux is permissive, Data encryption is unsupported, Verified
Boot is disabled, and kernel/vendor components are old. See [known issues and test
scope](docs/KNOWN_ISSUES.md).

R4 uses development signing keys. A clean R4 install followed by the separate
MindTheGapps Android 16 ARM64 add-on booted. Google Apps remain incompletely
qualified: Speech Services and Digital Wellbeing had Direct Boot failures
before the first user unlock. R8's bounded package/runtime check after normal
unlock passed, but did not establish Google account setup, sign-in, Play Store
certification, downloads, or interactive functionality. Release signing and
qualification of the final signed package remain pending. Google
Apps are not included in the ROM build. No public download or OTA service is
configured by this repository.

## Source snapshot

- Base lock: `manifests/base-source-lock.xml`, 1,174 pinned projects.
- Port snapshot: `patches/index.json`, 25 changed projects. Seven source
  projects changed between frozen R4 and R8; the final source export passed 25
  patch round-trip checks.
- Source forks: [the source map](docs/SOURCES.md).
- Fully tested R4 ZIP SHA-256:
  `ad7115e2548aa765ca4e1373ad448aa8f273268df364b6c0e1aab538c1277cfa`.
- Offline-reviewed R8 ZIP SHA-256:
  `87798ad7a2c0b1e8f9b56d6af73c970fb6ddb00232cd36b7eaff723f5b434336`.

The R8 source patches round-tripped against pinned project trees. The isolated
#15 Boot trial passed a direct scheduled-scan check (capacity 16, one SSID and
one match set) and a screen-off saved-network rejoin in 1.1 seconds. Twelve
USB-polled samples remained connected over 60 seconds. It does not establish
deep-sleep or overnight behavior or explain the earlier overnight disconnect.
The subsequent R8 install, targeted file checks, and first Android boot passed,
but do not replace physical accessory or broad application testing. A full
build from a second fresh checkout and byte-for-byte reproducibility have
not been performed. Build dates,
signing and packaging may change artifact hashes.

## Credits and licenses

Thanks to awesometic for the original device, kernel, vendor and recovery work;
to LineageOS, AOSP, Samsung, Qualcomm and other upstream contributors.

[Original Tab S3 ROM thread](https://xdaforums.com/t/rom-unofficial-14-eas-ota-sm-t820-sm-t825-2024-3-9-lineageos-21-for-galaxy-tab-s3.4660924/).

Build-root orchestration and documentation are licensed under Apache-2.0.
Patched upstream code retains its own licenses. The kernel is GPLv2; vendor
binaries retain their existing distribution terms. See [NOTICE](NOTICE).

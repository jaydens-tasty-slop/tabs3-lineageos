# LineageOS 23.2 for Samsung Galaxy Tab S3

Podman build instructions and source changes for **Android 16 on SM-T820
(`gts3lwifi`)**. This is an unofficial experimental port based on awesometic's
Tab S3 sources. SM-T825/LTE is not qualified.

The **HARDWARE-R4** clean-install path and the **HARDWARE-R8** full-ZIP dirty
upgrade have both booted on an SM-T820 through the maintainer's **TWRP
3.7.0_9-0 without-encryption** recovery build. Encrypted Data is unsupported.
A clean R8 installation has not been qualified.
R8 passed offline source, image-delta and module reviews. Its #15 kernel passed
a bounded Boot/PNO/rejoin trial: the screen-off saved-network rejoin took 1.1
seconds, and twelve samples over 60 seconds stayed connected with the display
off. That USB-polled trial does not establish deep-sleep or overnight behavior.
The R8 dirty upgrade passed targeted read-only post-install checks and booted
Android 16; its first boot completed in about 121 seconds, followed by a
30-second stable monitor interval. See [the installation guide](docs/INSTALLING.md)
for the tested R8 dirty-upgrade procedure and clean-install limits. These
bounded checks do not establish full application or accessory qualification.

The privately signed candidate `23.2-20261009_140353-UNOFFICIAL-gts3lwifi`
uses a persistent `jaydenmilne` signing identity and kernel
`3.18.140-jaydenmilne-tabs3-v1+`. Its offline checks passed for APK/APEX
signatures, APEX payload AVB signatures, OTA trust and signature, and the
source/System/Boot/OTA ADB cleanup gate. A clean install with separate
MindTheGapps completed through TWRP; Android boot and runtime checks of this
exact signed ZIP remain pending. Historical qualification below applies to the named older
packages. Double-tap-to-wake is disabled in the inherited device configuration.

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
builds, the offline ADB release gate, artifact locations, the read-only device
smoke check, optional media/GPU smoke, and unplugged sleep-study targets.

The checkout is reconstructed with **Android `repo`, a pinned manifest and
versioned patches**. There are no Git submodules. The device, kernel and vendor
forks provide convenient source review. Their prepared tips preserve the R8
repairs; the common-device tip also removes the temporary forced-ADB rule from
the later cleanup export. The complete 25-project patch snapshot and 1,174
pinned base revisions are the canonical reconstruction path. All Android
projects are Git clones.

## Historical qualification

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
launcher. The a035 keylayout maps Lang to LANGUAGE_SWITCH. The owner reported
Shift+2 produced a double quote and pressing Lang again restored @, though
there is no clear visual indication. No synchronized IME subtype/KCM readback
confirmed the selected layouts. A read-only check confirmed the selected
System keylayout, but the reconnect capture was not event-aligned and does not
prove the physical behavior is fixed; key 706 show/hide remains unmapped.

After normal unlock, bounded Google package/runtime checks passed, but account
setup, Play Store certification/downloads and interactive behavior remain
unverified. The first foreground batch was inconclusive because of a staging
path mismatch and inventory/APK-install failures. Corrected R8 checks passed
GLES2/3 drawing, ES3.1 compute, WebView JavaScript, and 32 generated decoder
executions across 19 cases. Nine additional moving AVC/HEVC clips ran for 20
seconds each, including 1080p60, 4K30 and HEVC Main10; all nine completed with
expected output frames. Qualcomm AVC and HEVC encoder outputs each contained
30 frames that independent host decoding checked against reference pixels.

The strict media inventory remains incomplete: 16 of 21 expected vendor
components are advertised, with four nonsecure and one secure legacy VC-1/DivX
component absent. Fixture success does not establish secure playback, DRM, HDR,
sustained performance, paced 60 fps, or hardware decoding of every frame.
Chrome 154 passed a generated JavaScript/WebGL fixture on Adreno 530 and
completed 20-second AVC/HEVC 1080p60 clips with expected pixel samples. AVC
reported 12 dropped of 1,200 frames and HEVC 8 of 1,200, with 897 and 892 frame
callbacks. These counters do not establish paced 60 fps or prove hardware
decoding for every frame. The audio API check confirmed sample acceptance on
the speaker route, not human audibility after the R8 boot.

An unplugged overnight R4 observation lasted about 12 hours 19 minutes:
battery 100% to 98%, approximately 98.8% kernel suspend, no reboot. Wi-Fi was
disconnected for about 4 hours 53 minutes and rejoined when the screen woke.
This does not establish continuously connected standby behavior.

**Open issues:** deep-sleep and overnight Wi-Fi behavior, occasional app-switch
stutter, five missing legacy media components, residual browser frame drops, a
clipped Lineage onboarding screen-lock heading, and camera quality/long-session
checks. R8 includes a new kernel #15 and audio/input changes. Its bounded media
fixtures passed, but secure playback, DRM/HDR, sustained performance, paced
60 fps, and hardware decoding of every frame remain unqualified. Launcher
Search, exact language-subtype selection, owner-confirmed post-upgrade audio,
and broader application behavior also remain open. The owner reported that
Lang restored `@` after Shift+2 produced a quote, but no synchronized IME
subtype/KCM readback was captured.
SELinux is permissive, Data encryption is unsupported, Verified
Boot is disabled, and kernel/vendor components are old. See [known issues and test
scope](docs/KNOWN_ISSUES.md).

Earlier ROM artifacts used development signing keys. The new candidate uses
our persistent private signing keys, with the standard Android `release-keys`
tag. Settings Build number shows Android's platform ID `BP4A.251205.006`; the
LineageOS version contains the build date. A clean reset is required for this
transition from development keys. Future updates must retain the same signing
identity. The ordinary build targets still produce development-signed output;
see [signing](docs/SIGNING.md) before distributing your own builds.

A clean R4 install followed by
the separate MindTheGapps Android 16 ARM64 add-on booted. Some Google extras
logged startup failures before the first user unlock; bounded package/runtime
checks after normal unlock passed. They do not establish Google account setup,
sign-in, Play Store certification, downloads or interactive functionality.
Google Apps are not included in the ROM ZIP. Persistent signing keys have been generated and backed up privately;
qualification of the exact signed candidate remains pending. No public download or OTA service is configured by this repository.

## Source snapshot

- Base lock: `manifests/base-source-lock.xml`, 1,174 pinned projects.
- Port snapshot: `patches/index.json`, 25 changed projects. Seven source
  projects changed between frozen R4 and R8; the final source export passed 25
  patch round-trip checks.
- Source forks: [the source map](docs/SOURCES.md); convenience tips preserve the
  R8 repairs, with the common-device tip also carrying the later forced-ADB
  cleanup export.
- R4 clean-install-tested ZIP SHA-256:
  `ad7115e2548aa765ca4e1373ad448aa8f273268df364b6c0e1aab538c1277cfa`.
- R8 dirty-upgrade-tested ZIP SHA-256:
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

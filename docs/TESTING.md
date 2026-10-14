# Android 17 qualification suite

The public harness uses pytest as the coordinator while retaining the bounded,
device-specific probes that produce detailed JSON evidence. A normal run prints
ordinary pytest progress and ends with both `summary.json` and `junit.xml` under
a new private `diagnostics/` directory. Each test is reported as pass, fail or
skip; a failure names its complete log rather than reducing the result to a
single opaque exit code.

The suite never embeds an ADB key, account credential, device serial or licensed
media. APKs and video fixtures are generated locally from published source.
Probe APKs use a throwaway local key and are removed when the individual probe
installed them. Tests preserve and restore the USB stay-awake setting.

## Quick release gate

Build the ROM once, boot Android 17, complete setup, enable USB debugging, and
unlock the tablet. With exactly one authorized tablet, run:

```sh
make test-quick
```

This builds the small synthetic payload set and checks platform identity/core
services, Widevine capabilities, generated AVC/HEVC/AAC decode, GLES, WebView,
an AudioTrack route and Vulkan compute. It requires ordinary shell ADB, not root
ADB.

## Full generated-media and camera suite

```sh
make test-full
```

The full profile includes the quick profile, all 19 generated clear-codec cases,
hardware AVC/HEVC encoders with independent FFmpeg verification, three Widevine
L1 secure-HEVC controls, microphone/sensor/camera I/O, ordinary-app network
permission enforcement and UID accounting, Camera2 preview/JPEG/direct/drained
close cycles on both cameras, and a two-minute framework stability window. It
can take substantially longer and needs the screen to remain normally unlocked.

The secure controls use clear synthetic samples through an L1 MediaCrypto
session and protected surface. They exercise the secure decoder/CSD path but do
not replace licensed streaming tests.

## Browser and ordinary-app profile

This profile downloads four APKs through F-Droid's signed index, verifies their
hashes and signatures, and leaves those ordinary apps installed for the owner.
It requires a shared Wi-Fi LAN between host and tablet and uses three public
Internet pages:

```sh
make test-browser
```

It runs CPU Info launch/inventory, a one-minute bounded DroidStress workload,
generated browser video fixtures, public HTTPS pages, and warm app/home frame
statistics. The local fixture records JavaScript frame results and observes the
Qualcomm video device descriptor when permissions allow. The harness does not
log into an account or submit personal data. If more than one device is
connected, add `SERIAL=<adb-serial>` to any command.

## Reading results

The command exits zero only when every selected automated check passes. Its last
line names `diagnostics/<run>/summary.json`; that file contains the exact command,
overall result, and one row per test. `junit.xml` in the same directory is ready
for CI systems. Each pytest failure prints the corresponding complete log path,
while the device-specific probes retain richer JSON, logcat, screenshots, and
codec evidence in adjacent timestamped directories. Skips are reported
separately and never counted as passes.

The `test-*` targets rebuild their small tools images through Podman's cache, so
a pulled dependency change cannot silently reuse an older test environment.

## Manual release checks

Automation cannot establish physical speaker quality, microphone audibility,
touch alignment, fingerprint enrollment UX, flashlight output, licensed DRM
policy, HDR appearance, or camera image quality. Record those separately for the
exact candidate. In particular, test Aperture front/rear still capture, 1080p
video and its resolution menu; stock firmware's 4K30 capability is an explicit
open target. Test licensed Widevine playback without publishing account data or
copyrighted content.

Generated APKs, fixtures, downloaded F-Droid packages and all results remain in
ignored `artifacts/`, `state/` and `diagnostics/` paths. See
[test scope and known issues](KNOWN_ISSUES.md) before interpreting a passing run
as broader certification.

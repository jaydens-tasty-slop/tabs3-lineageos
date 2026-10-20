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
installed them. The media probe requests only the Android `INTERNET` permission.
With explicit operator opt-in, a clean data partition may send the Widevine
HAL's vendor-generated provisioning request to the vendor-provided HTTPS
endpoint. That request may contain a device-specific DRM credential or
identifier. The probe records only the host/status/byte counts and never
requests a media license. Tests preserve and restore the USB stay-awake setting.

## Quick release gate

Build the ROM once, boot Android 17, complete setup, enable USB debugging, and
unlock the tablet. With exactly one authorized tablet, run:

```sh
make test-quick
```

This builds the small synthetic payload set and checks platform identity/core
services, Widevine capabilities, generated AVC/HEVC/AAC decode, GLES, WebView,
an AudioTrack route and Vulkan compute. It requires ordinary shell ADB, not root
ADB. On the first run after a data wipe, the DRM check reports that provisioning
is required without transmitting the request. After reviewing the disclosure
above, explicitly allow vendor provisioning requests with working Internet:

```sh
TAB_S3_PROVISION_WIDEVINE=1 make test-quick
```

A successful request normally persists in the HAL, so later runs do not need
the opt-in. A failed attempt can be retried by a later DRM probe while opt-in
remains enabled.

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

The network-policy check intentionally runs immediately after platform smoke.
On this legacy adbd, ordinary shell ADB can remain healthy while reverse TCP
forwarding stops accepting connections after sustained media/camera workloads.
If a previously interrupted or standalone reverse test leaves that path stale,
the report explains that the tablet must be rebooted before retrying. Diagnostic
APKs always use non-streaming installs to avoid Android 17 Package Installer
session hangs.

The secure controls use clear synthetic samples through an L1 MediaCrypto
session and protected surface. They exercise the secure decoder/CSD path but do
not replace licensed streaming tests.

## Browser and ordinary-app profile

This profile downloads five APKs through F-Droid's signed index, verifies their
hashes and signatures, and leaves those ordinary apps installed for the owner.
It requires a shared Wi-Fi LAN between host and tablet and uses three public
Internet pages:

```sh
make test-browser
```

It runs CPU Info launch/inventory, a one-minute bounded DroidStress workload,
generated browser video fixtures in both Fennec and FOSS Browser, public HTTPS
pages, and warm app/home frame statistics. Fennec's documented Android
video-to-Canvas limitation is accepted only when both videos finish with
bounded drops and no media error, all non-video checks pass, and every sampled
video pixel is exactly transparent; the report calls this limitation out and
does not claim per-frame hardware decoding. FOSS Browser must independently
pass opaque generated-video pixel checks. The local fixture also observes the
Qualcomm video device descriptor when permissions allow. The harness does not
log into an account or submit personal data. If more than one device is
connected, add `SERIAL=<adb-serial>` to any command.

Fresh-install automation handles only the specifically recognized Fennec and
FOSS Browser welcome screens. It never accepts permission, default-browser,
certificate or TLS prompts. USB stay-awake is applied for the run and restored
afterward, but the owner profile must be normally unlocked before preflight.

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
An exclusive buildroot lock rejects concurrent qualification runs before they
can compete over temporary APK installation.

During an incomplete first boot, Android 17's upstream Device Diagnostics may
advertise a restricted Trade-In Mode ADB transport. It intentionally rejects
ordinary shell commands and is not Developer Options debugging. The wrapper
detects the missing UID-2000 shell and explains that setup/connectivity must be
completed before enabling normal USB debugging; toggling debugging off/on also
clears a stale host transport.

## Manual release checks

Automation cannot establish physical speaker quality, microphone audibility,
touch alignment, fingerprint enrollment UX, flashlight output, licensed DRM
policy, HDR appearance, or camera image quality. Record those separately for the
exact candidate. In particular, test Aperture front/rear still capture, 1080p
video and its resolution menu. Candidate source restores stock firmware's 4K30
mode; the exact candidate recorded and played a valid nominal-30-fps UHD clip
before the final clean install. Repeat that check after a clean install. Test
licensed Widevine playback without publishing account data or copyrighted
content.

Generated APKs, fixtures, downloaded F-Droid packages and all results remain in
ignored `artifacts/`, `state/` and `diagnostics/` paths. See
[test scope and known issues](KNOWN_ISSUES.md) before interpreting a passing run
as broader certification.

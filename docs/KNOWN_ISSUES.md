# Test scope and known issues

This release is qualified on **SM-T820 Wi-Fi only**. Results cover one tablet.
An **SM-T825/LTE (`gts3llte`) build is also produced but is essentially untested**:
a user reports it boots, but the maintainer has not run it, and the Qualcomm
MSM8996 modem/QMI RIL stack is unverified and probably does not work. SM-T825
reports (logcat, `dmesg`) are welcome.

SM-T825 notes: the Samsung `vendor.samsung.hardware.radio.configsvc@1.0`
HIDL interface exists only in the vendor blobs. Android 17's init verifier
needs a definition, so `hardware/samsung` carries a `hidl_interface` rebuilt
from the blob's exported symbols (`getTdfValue`, `updateTotalCallTime`) that
is used only for the build check; the blob implements it at runtime. The
vendor RIL is Android 9-era and the framework expects newer radio HALs, so
registration with the telephony stack is the most likely failure. Google Apps are optional and separately installed.

## Android 17 candidate status

The final maintainer-signed Android 17 package was reconstructed from the public
source lock and patches, clean-installed with Android 17 GApps, and passed boot
plus the complete 13/13 generated-media/camera qualification profile. The
identical-source predecessor passed the browser/app profile 6/6; the owner
waived repeating that profile for the signing-only final package. Some physical
and interactive paths listed below remain outside the release gate.

Widevine remains L1 in development testing. After a Qualcomm secure-HEVC CSD
compatibility repair, generated protected streams and licensed Apple TV
playback—including 1080p SDR and cached HDR content—played without the prior
Venus decoder corruption. The baked package passed generated L1 secure-HEVC
Main/Main10 controls and licensed Apple TV playback adapted across multiple
protected 1080p-class representations without the prior decoder failure; the
owner reported clean picture and audio. Stock firmware's 4K30 camera mode is
restored: the exact candidate opened its resolution menu without crashing and
recorded a valid H.264 3840x2160, nominal-29.92-fps clip with stereo AAC. The
owner reported clean playback, and an independent FFmpeg decode completed
without error.

The release gate requires `ro.secure=1`, `ro.adb.secure=1`,
`ro.debuggable=0`, no embedded host ADB authorization key, matching built and
OTA Boot/System payloads, and a successful clean installation.

The tablet's legacy adbd can keep ordinary shell ADB working while a reverse
TCP mapping silently stops forwarding after sustained media/camera workloads.
The public full suite runs its reverse-dependent network-policy check before
those workloads and reports an explicit reboot instruction if stale reverse
state is detected. This affects host-side test ordering, not normal device
networking; the same clean-installed candidate passed ordinary-app INTERNET
permission enforcement, UID accounting, browser LAN fixtures and public HTTPS.

## Historical Android 16 checks

The prior privately signed Android 16 release passed a clean installation and
a same-key TWRP update with separate MindTheGapps. It passed bounded boot,
core-process, bitmap, Settings/Wellbeing, offline TTS, hardware and media tests.
An unplugged observation lasted **11h48m**, with battery **100% → 98%**,
unchanged boot/core identities and no recorded fatal crash. One AP-initiated
inactivity disconnect recovered with the screen off in about one second. These
results guide Android 17 retesting but do not qualify the current artifact.

The sleep endpoints included approximately 26 minutes of USB recharging;
retained battery history established the actual precharge readings. Kernel
clocks measured about 11h39m suspended, 95.1% of the full 12h15m observation
bracket including USB. That percentage is not the exact unplugged suspend
fraction. There were 500 successful and 124 failed suspend attempts, no failed
resumes, and 1,654 RPM vmin entries. One observation does not establish every
driver transition, multi-day standby or that the scheduled-scan changes caused
the improvement.

## Earlier hardware checks

Broader tests ran on earlier development builds and have not all been repeated
on the exact signed ZIP. They provide useful coverage without transferring
complete qualification to a new package.

| Area | Observed coverage | Remaining limits |
| --- | --- | --- |
| Input | Touch, S-Pen, fingerprint, buttons and haptics; owner reports | Palm rejection and every accessory transition are not fully qualified |
| Connectivity | Wi-Fi traffic/reconnect; owner verified Bluetooth pairing | All access points, profiles and prolonged sessions are not qualified |
| Audio | Speaker/headphone playback, microphone capture; owner reports and bounded probes | Voice/video-call routing, all DSP paths and current-release audibility are not fully qualified |
| Video | Generated AVC/HEVC decoder cases, 1080p60/4K30 decode fixtures, protected HEVC controls and licensed Widevine L1 playback on the exact candidate | Paced 60 fps, sustained protected playback and HDR output are not qualified |
| Encoding | Qualcomm AVC and HEVC encoders produced 30-frame outputs verified by independent host decoding | Long recordings and every rate/profile are not qualified |
| Graphics | GLES2/3 drawing, ES3.1 and Vulkan compute; Chrome WebGL on Adreno 530 | Vulkan presentation, games and sustained workloads are not qualified |
| Web | Local WebView/Chrome JavaScript and media fixtures | Browser frame drops remain; frame counters do not prove hardware decode for every frame |

The exact latest package passed the public FOSS Browser generated-video,
WebGL 1/2 and HTTPS controls. Fennec 157 played both generated videos to
completion but reproduced its inherited Android video-to-Canvas transparent
pixel limitation; the harness accepts only that exact bounded profile and
reports it explicitly.

The decoder suite passed 32 executions across 19 generated cases and nine
additional moving AVC/HEVC clips. The strict component inventory remains
incomplete: 16 of 21 expected vendor components are advertised, with four
nonsecure and one secure legacy VC-1/DivX component missing.

## Open issues

- **Setup layout:** the Choose screen lock heading/subtitle can be clipped
  during Lineage onboarding. The ordinary Settings lock picker looked normal.
- **Stutter:** occasional app-switch jank and browser dropped frames remain,
  including with GApps. Measurements did not establish sustained severe memory
  exhaustion as their cause.
- **Audio routing:** a repair recovered headphone-to-speaker routing during
  physical plug/unplug trials. The original cause remains uncertain; repeated
  cycles after each release and voice/video-call paths need more coverage.
- **Samsung EJ-FT820 cover:** Search works in Chrome but is inert in the
  launcher. Lang switches layouts without a clear visual indication; the
  owner restored US `@` after accidentally selecting another layout. A narrow
  EventHub filter handles Samsung switch code 21 and passed a synthetic
  regression test; broader physical reconnect coverage remains limited.
  The code-706 keyboard show/hide key remains unmapped.
- **Camera quality/endurance:** colors, the originally reported webcam green
  bar, long sessions, repeated cold boots and wider third-party use remain
  unqualified. Do not assume the original maintainer's camera issues are fixed.
- **Unqualified hardware paths:** GPS fix, sustained protected streaming, HDR
  output on the final package, USB OTG, powered-off charging and voice/video
  calls.
- **Double-tap-to-wake:** disabled in the inherited configuration. Actual
  Tab S3 touchscreen firmware support has not been established.
- **Android Linux Terminal:** unsupported; the kernel does not enable
  `CONFIG_VIRTUALIZATION` and the Android virtualization feature is unavailable.

## Google Apps and inherited limits

The clean candidate boots with the unmodified official Android 17 MindTheGapps
package. Google account setup, sign-in, Play Store certification, downloads and
broad interactive Google Apps behavior remain only partially qualified; do not
reuse the Android 16 package.

SELinux is **permissive**, Data encryption is **unsupported**, and Android
Verified Boot is **disabled**. Samsung/Qualcomm kernel and vendor components
remain old; the vendor security baseline is March 2020. A current Android
framework patch level does not replace that older kernel/vendor baseline.

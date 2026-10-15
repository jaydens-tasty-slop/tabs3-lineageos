# Test scope and known issues

This release targets **SM-T820 Wi-Fi only**. Results cover one tablet;
SM-T825/LTE is unsupported. Google Apps are optional and separately installed.

## Android 17 candidate status

The final Android 17 package is not yet published. A package reconstructed from
the public source lock and patches has passed ROM/GApps installation, boot, the
complete generated-media/camera qualification profile, and the browser/app
profile. Some physical and interactive checks below remain before publication;
the latest camera-race rebuild was installed as a data-preserving update over
the clean candidate and still needs the final clean-install repetition.

Widevine remains L1 in development testing. After a Qualcomm secure-HEVC CSD
compatibility repair, generated protected streams and licensed Apple TV
playback—including 1080p SDR and cached HDR content—played without the prior
Venus decoder corruption. The baked package passed generated L1 secure-HEVC
Main/Main10 controls; licensed Apple TV playback still needs the final manual
repeat. Stock firmware's 4K30 camera mode is restored in candidate source and
passed on a development build; the exact latest package still needs the manual
UHD30 recording check.

The release gate requires `ro.secure=1`, `ro.adb.secure=1`,
`ro.debuggable=0`, no embedded host ADB authorization key, matching built and
OTA Boot/System payloads, and a successful clean installation.

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
| Video | Generated AVC/HEVC decoder cases, 1080p60/4K30 decode fixtures, protected HEVC controls and licensed Widevine L1 playback on development builds | Final-package secure playback, paced 60 fps and sustained performance are not qualified |
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

# Test scope and known issues

This release targets **SM-T820 Wi-Fi only**. Results cover one tablet;
SM-T825/LTE is unsupported. Google Apps are optional and separately installed.

## Exact release checks

`lineage-23.2-20261010_003605-UNOFFICIAL-gts3lwifi.zip` uses private persistent
signing keys and kernel `3.18.140-jaydenmilne-tabs3-v1+`, #17.

- Offline source, System/Boot/OTA, APK/APEX signature, APEX payload and ADB
  cleanup audits passed. All 34 APEX modules became active after boot.
- A same-key TWRP update preserved the separately installed MindTheGapps
  add-on. Boot completed in about 111 seconds. The previous signed build
  passed a clean installation; this exact ZIP's clean install is untested.
- All 20 arm32/arm64 bitmap roundtrips and ten ordinary-app bitmap cases
  passed. Settings → Users, Digital Wellbeing and offline Google TTS worked
  after normal unlock. Bounded core-process checks passed with no crash-buffer
  entries at the final capture.
- An unplugged observation lasted **11h48m**, with battery **100% → 98%**,
  unchanged boot/core identities and no recorded fatal crash. One AP-initiated
  inactivity disconnect recovered with the screen off: IP configuration in
  683 ms and validated internet in 993 ms. The older multi-hour Wi-Fi outage
  did not recur during this interval.

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
| Video | Generated AVC/HEVC decoder cases and 20-second 1080p60/4K30 clips, including HEVC Main10 | Secure playback, DRM, HDR, paced 60 fps and sustained performance are not qualified |
| Encoding | Qualcomm AVC and HEVC encoders produced 30-frame outputs verified by independent host decoding | Long recordings and every rate/profile are not qualified |
| Graphics | GLES2/3 drawing, ES3.1 and Vulkan compute; Chrome WebGL on Adreno 530 | Vulkan presentation, games and sustained workloads are not qualified |
| Web | Local WebView/Chrome JavaScript and media fixtures | Browser frame drops remain; frame counters do not prove hardware decode for every frame |

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
- **Unqualified hardware paths:** GPS fix, Widevine level, protected streaming,
  HDR output, USB OTG, powered-off charging and voice/video calls.
- **Double-tap-to-wake:** disabled in the inherited configuration. Actual
  Tab S3 touchscreen firmware support has not been established.
- **Android Linux Terminal:** unsupported; the kernel does not enable
  `CONFIG_VIRTUALIZATION` and the Android virtualization feature is unavailable.

## Google Apps and inherited limits

A prior signed clean install with MindTheGapps Android 16 ARM64 booted. The
exact release retained that add-on through a same-key update and passed scoped
post-unlock Settings/Wellbeing/TTS checks. Some Google extras previously logged
startup errors before the first unlock. Google account setup, sign-in, Play
Store certification/downloads and broad interactive Google Apps behavior remain
unqualified.

SELinux is **permissive**, Data encryption is **unsupported**, and Android
Verified Boot is **disabled**. Samsung/Qualcomm kernel and vendor components
remain old; the vendor security baseline is March 2020. A current Android
framework patch level does not replace that older kernel/vendor baseline.

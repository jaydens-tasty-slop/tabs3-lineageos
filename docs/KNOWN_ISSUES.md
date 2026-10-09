# R4 qualification and R5 source-candidate status

Device: SM-T820 (`gts3lwifi`). Framework: LineageOS 23.2 / Android 16.
Kernel: 3.18.140. Last reviewed: October 9, 2026.

## Observed working operations

| Area | Evidence and limits |
| --- | --- |
| Boot and installation | Exact R4 TWRP ZIP boots; installed System file contents and Boot match the package. Recovery was preserved. A later Data/Cache reset plus separate MindTheGapps Android 16 ARM64 installation booted; add-on validation remains ongoing. The R5 source candidate has not been qualified by a full ZIP install/boot. |
| Camera | R4+GApps bounded regression so far passes Camera2 full-size JPEG on both cameras (rear 4128×3096, front 2560×1920), Camera1 1920×1080 JPEGs, short AVC/HEVC camera video and two-cycle front/rear WebView camera streams. The camera review is still in progress. Quality, green-bar behavior, long sessions and repeated cold boots remain unqualified. |
| Wi-Fi | Enables, scans, connects, transfers LAN traffic with UID accounting, and reconnects while awake. Screen-off reconnect is an open issue below. |
| Video hardware | R4 checks covered nine moving decoder cases, including H.264/HEVC 1080p60 and 4K30, and HEVC Main10; five hardware encoders with independent decoding. Advertised hardware components were observed. |
| Browser | On R4+GApps, Chrome 154 passed a generated local-page JavaScript/WebGL fixture using ANGLE/Adreno 530 and coarse pixel checks for generated 20-second 1080p60 AVC/HEVC clips. AVC reported 125/1,200 dropped frames (930 callbacks); HEVC reported 39/1,200 (638 callbacks). This does not establish paced 60 fps or prove per-frame hardware decoding. |
| Audio | Existing R4 PCM speaker, microphone and DSP playback checks pass. With a temporary runtime audio-policy candidate, two physical headphone plug/unplug cycles retained the expected primary route. The owner confirmed website audio audible through headphones and then through speakers after unplug in the second cycle. The candidate's source integration and exact bool property context passed export/round-trip and targeted property/context build checks; a complete R5 ROM build/install/boot is pending. |
| Graphics and apps | R4 bounded GLES shader/blit/compute and Vulkan compute, sensor delivery and local WebView checks passed. These checks do not establish full application performance. |
| Input | Owner verified touch, fingerprint reader, buttons, haptics, S-Pen and flashlight. Palm rejection and pen side-button behavior need application-specific checks. |
| Bluetooth | Owner verified pairing. Media playback/reconnect and headset microphone routing are unqualified. |
| Standby | One overnight R4 interval: about 12 h 19 min, 100% to 98%, about 98.8% kernel suspend, no reboot. The network was disconnected for about 4 h 53 min. |

## Open issues

- **Screen-off Wi-Fi:** scheduled scans fail with `EINVAL` in a controlled test.
  A disconnected saved network may wait until the display wakes to rejoin. The
  overnight study also showed delayed rejoining. The initial overnight
  disconnect cause has not been established.
- **Stutter and memory:** occasional app-switch jank and browser dropped frames
  remain. A six-sample post-GApps capture measured about 1.33–1.72 GiB
  MemAvailable and modest direct-reclaim/allocation-stall activity late in the
  sample while app optimization and Play Store CPU work were present. It did
  not show severe sustained memory exhaustion, and it does not establish a
  cause for jank. The Chrome frame counters are fixture results, not a paced
  display benchmark.
- **Camera quality/endurance:** colors, green-bar behavior, longer sessions,
  repeated cold boots and wider third-party use remain under review. The
  original maintainer reported webcam color problems; do not assume they are
  fixed.
- **Setup layout:** the Choose screen lock heading/subtitle can be clipped in
  LineageOS onboarding. The standard Settings screen-lock picker was observed
  without the clipping; the onboarding layout remains under review.
- **Browser Canvas:** Fennec displays generated videos but video-to-Canvas reads
  return transparent pixels. FOSS Browser passes the corresponding fixture.
- Four advertised legacy VC-1/DivX components remain unavailable.
- GPS fix, Widevine level, protected streaming, HDR output, USB OTG,
  powered-off charging and voice/video calls are not fully qualified.
- Google Apps, Magisk and a public OTA channel are not qualified.
- **R5 audio source integration:** targeted `system-build.prop` and
  `plat_property_contexts` outputs verify the opt-in property and exact bool
  context. The source update has not yet been through a full ROM package,
  installation or boot qualification. The underlying audio issue's cause is
  not established; no GApps causal relationship is established.

## Inherited platform limits

SELinux is permissive, Data encryption is unsupported and Android Verified Boot
is disabled. The Samsung/Qualcomm kernel and vendor components remain old; the
vendor security baseline is March 2020. A current framework patch date does not
update those components. The fully tested R4 build uses development signing
keys.

Tests so far cover one tablet and bounded sessions. Final release signing,
clean installation of the final signed package and repeated cold-boot checks
remain pending. This is an unofficial experimental port, with no SM-T825/LTE
support claim.

## Separate Google Apps follow-up

A clean R4 install plus MindTheGapps Android 16 ARM64 20260915 booted. The core
Google APKs match the separate add-on and System passes a read-only filesystem
check. Speech Services and Digital Wellbeing crashed during the first boot
before user unlock with an error about credential-protected storage. Recovery
after unlock, onboarding, account services, Play Store downloads/certification
and Google Apps standby behavior are still being checked. This observation does
not establish Google Apps compatibility.

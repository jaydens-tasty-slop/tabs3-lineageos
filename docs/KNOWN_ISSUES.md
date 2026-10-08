# R4 qualification and known issues

Device: SM-T820 (`gts3lwifi`). Framework: LineageOS 23.2 / Android 16.
Kernel: 3.18.140. Last reviewed: October 8, 2026.

## Observed working operations

| Area | Evidence and limits |
| --- | --- |
| Boot and installation | Exact R4 TWRP ZIP boots; installed System file contents and Boot match the package. Recovery was preserved. A subsequent Data/Cache reset plus separate GApps install booted; add-on validation is ongoing. |
| Camera | 30 decoded rear/front JPEGs, including maximum resolution; Camera1 release/reopen; short AVC/HEVC video sessions; four local WebView camera streams. Ordinary SDK tests passed without provider/framework restart. |
| Wi-Fi | Enables, scans, connects, transfers LAN traffic with UID accounting, and reconnects while awake. Screen-off reconnect is an open issue below. |
| Video hardware | Nine moving decoder cases, including H.264/HEVC 1080p60 and 4K30, and HEVC Main10; five hardware encoders with independent decoding. Advertised hardware components were observed. |
| Audio | PCM speaker routing, four microphone modes, eight MP3/AAC DSP playback combinations; owner verified wired headphones and speakers. Voice/video call routing is unqualified. |
| Graphics and apps | GLES shader/blit/compute and bounded Vulkan compute; sensor delivery, local WebView and F-Droid browsing/graphics checks. Performance limits remain. |
| Input | Owner verified touch, fingerprint reader, buttons, haptics, S-Pen and flashlight. Palm rejection and pen side-button behavior need application-specific checks. |
| Bluetooth | Owner verified pairing. Media playback/reconnect and headset microphone routing are unqualified. |
| Standby | One overnight interval: about 12 h 19 min, 100% to 98%, about 98.8% kernel suspend, no reboot. The network was disconnected for about 4 h 53 min. |

## Open issues

- **Screen-off Wi-Fi:** scheduled scans fail with `EINVAL` in a controlled test.
  A disconnected saved network may wait until the display wakes to rejoin. The
  overnight study also showed delayed rejoining. The initial overnight disconnect
  cause has not been established.
- **Stutter:** occasional app-switch jank and browser dropped frames remain.
  Bounded GPU and hardware codec passes do not establish smooth 60 fps rendering.
- **Camera quality/endurance:** colors, green-bar behavior, longer sessions,
  repeated cold boots and wider third-party use remain unqualified. The original
  maintainer reported webcam color problems; do not assume they are fixed.
- **Setup layout:** the Choose screen lock heading/subtitle can be clipped.
- **Browser Canvas:** Fennec displays generated videos but video-to-Canvas reads
  return transparent pixels. FOSS Browser passes the corresponding fixture.
- Four advertised legacy VC-1/DivX components remain unavailable.
- GPS fix, Widevine level, protected streaming, HDR output, USB OTG,
  powered-off charging and voice/video calls are not fully qualified.
- Google Apps, Magisk and a public OTA channel are not qualified.

## Inherited platform limits

SELinux is permissive, Data encryption is unsupported and Android Verified Boot
is disabled. The Samsung/Qualcomm kernel and vendor components remain old;
the vendor security baseline is March 2020. A current framework patch date does
not update those components. The current R4 build uses development signing keys.

Tests so far cover one tablet and bounded sessions. Final release signing,
clean installation of the final signed package and repeated cold-boot checks remain pending. This is an
unofficial experimental port, with no SM-T825/LTE support claim.


## Separate Google Apps follow-up

A clean R4 install plus MindTheGapps Android 16 ARM64 20260915 booted. The core
Google APKs match the separate add-on and System passes a read-only filesystem
check. Speech Services and Digital Wellbeing crashed during the first boot
before user unlock with an error about credential-protected storage. Recovery
after unlock, onboarding, account services, Play Store downloads/certification
and Google Apps standby behavior are still being checked. This observation does
not establish Google Apps compatibility.

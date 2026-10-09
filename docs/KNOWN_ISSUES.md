# R4 qualification and R8 installation review

Device: SM-T820 (`gts3lwifi`). Framework: LineageOS 23.2 / Android 16.
Kernel: 3.18.140, with R8 carrying a new #15 image. Last reviewed: October 9,
2026.

## Tested operations and current limits

| Area | Evidence and limits |
| --- | --- |
| Boot and installation | A clean R4 install plus the separate MindTheGapps Android 16 ARM64 add-on booted using the maintainer's TWRP 3.7.0_9-0 without-encryption build. The R8 dirty upgrade from that R4 Android 16 state completed through TWRP command-line and GUI success barriers; read-only checks passed for 27 changed System content/module/metadata entries and the three separate Google core APKs/add-on script. Android 16 first boot completed in about 121 seconds and remained stable for a 30-second monitor interval. Basic boot/service/APEX/package/crash-buffer smoke passed. The R8 clean-install path is not qualified. This is one bounded installation and boot, not broad application qualification. |
| Camera | Bounded R4+GApps review covered Camera2 full-size JPEGs on both cameras, Camera1 JPEGs, short AVC/HEVC video and two-cycle front/rear WebView camera streams. Colors, green-bar behavior, endurance and repeated cold boots remain open. |
| Wi-Fi | R4 enables, scans, connects, transfers LAN traffic with UID accounting, and reconnects while awake. A #13 kernel PNO/direct-scan and saved-network rejoin check passed in a short screen-off poll. R8 uses a distinct #15 kernel. Its Boot-only trial, with the R4 System unchanged, accepted a direct scheduled scan with capacity 16, one SSID and one match set; it stopped cleanly and preserved the existing connection. Android rejoined the same saved network with the display off in 1.1 seconds. Twelve USB-polled samples remained connected during a 60-second screen-off interval. This does not establish deep sleep or overnight behavior or explain the earlier overnight disconnect. |
| Video and browser | R4 checks covered moving decoder cases including H.264/HEVC 1080p60 and 4K30, HEVC Main10, and five hardware encoders with independent decoding. R8 passed 32 generated decoder executions across 19 cases, including Qualcomm AVC/HEVC, Main10 and software audio. Nine moving 20-second AVC/HEVC clips at 1080p60 and 4K30, plus HEVC Main10, completed with expected output frames. Qualcomm AVC and HEVC encoder outputs each produced 30 frames verified by independent host decode and reference-pixel comparison. The strict inventory remains incomplete: 16 of 21 expected vendor components are advertised; four nonsecure and one secure legacy VC-1/DivX components are absent. Chrome 154 passed a generated local JavaScript/WebGL fixture on Adreno 530 and completed 20-second AVC/HEVC 1080p60 clips with expected pixel samples. AVC reported 12/1,200 and HEVC 8/1,200 dropped frames, with 897/892 callbacks. These checks do not establish secure playback, DRM/HDR, sustained performance, paced 60 fps, or hardware decode of every frame. |
| Audio | R4 PCM speaker, microphone and DSP playback checks passed. A temporary audio-policy runtime candidate preserved the primary speaker route across two physical headphone cycles; the owner confirmed website audio through headphones and speakers after unplug. R8's changed library passed exact post-install file checks. A bounded foreground audio-route check reported the HAL accepted 96,000 samples on the speaker route, but owner confirmation of audibility after the R8 boot remains pending. |
| Graphics and input | R4 bounded GLES/Vulkan compute, sensor delivery and local WebView checks passed. The owner verified touch, buttons, haptics, S-Pen and flashlight. R8's synthetic SW_FLIP filter test passed with cleanup and stable core identities. The owner later reported multiple physical cover reconnects and Search working in Chrome, while launcher Search was inert. R8's a035 keylayout maps the physical Lang key to LANGUAGE_SWITCH. The owner later reported that Shift+2 showed a double quote and pressing Lang again restored @; there is no clear visual indication. This confirms the physical key changes the character layout in the owner's workflow, but no synchronized IME subtype/KCM readback was captured, so the exact selected layouts and cause are unverified. A read-only check confirmed the selected System keylayout. The reconnect capture was not event-aligned, so it does not prove that every physical transition followed the corrected path. A later metadata snapshot showed Spanish (US) current, English and Spanish eligible, and seven handled language-switch gestures; it did not compare before/after subtype. Launcher Search remains inert, key 706 show/hide remains unmapped, and the physical reconnect path remains partly unqualified. |
| Bluetooth and standby | Owner verified Bluetooth pairing. One unplugged overnight interval lasted about 12 h 19 min, battery 100% to 98%, approximately 98.8% kernel suspend, and no reboot. Wi-Fi was disconnected for about 4 h 53 min and rejoined when the display woke. |

## Replacement build offline package review

The replacement build `23.2-20261009_103849-UNOFFICIAL-gts3lwifi` removes the
temporary device-specific USB ADB activation rule and passed the offline
source/image/OTA ADB guard. It has not been installed or booted. The R8
installation, smoke and runtime results above refer to the earlier tested R8
ZIP and do not qualify this replacement artifact.

The frozen R8 ZIP passed package/provenance checks, a complete R4-to-R8 raw
System path/content/metadata comparison, a direct Boot/kernel/ramdisk binding,
source patch round-trips, static binary review and module-image reconciliation.
The full delta records 12 content changes and 7 metadata changes, with no
installer changes. The source export checked 25 projects; seven source projects
differ from frozen R4. Nine kernel modules and three module metadata files match
R4 in the final candidate image. The review does not exercise modules or prove
formal module ABI compatibility (`CONFIG_MODVERSIONS` is disabled).

R8 uses kernel #15, which is a distinct binary from the previously tested #13.
Matching configuration, DTBs and ramdisk did not transfer qualification. The
fresh #15 Boot trial and bounded PNO/screen-off rejoin passed, with cleanup and
rollback identities verified. Direct scan capacity was 16; the accepted
request used one SSID and one match set. The saved network rejoined with the
display off in 1.1 seconds, followed by twelve connected samples over 60
seconds. The interval was polled over USB and is not a deep-sleep or overnight
test, nor does it explain the earlier overnight disconnect. R8 has since been
installed, passed targeted post-install checks, and booted once; this bounded
test still does not establish overnight reconnect behavior.

The first read-only post-install check stopped before package-file checks
because TWRP reports the ext4 no-load option as `norecovery`. It removed its
temporary mount and confirmed Boot, System and Recovery hashes were unchanged.
The saved report contains an error despite a `complete` phase, so it is treated
as a failed attempt. The checker now accepts the documented `norecovery` alias
only with read-only mount options, retains the System image's `/system` prefix,
and reports completion only when all checks pass. The corrected retry passed 27
targeted System content/module/metadata checks and exact checks of the three
separate Google core APKs and add-on script. This verifier checks the selected
changed paths; it does not claim full-tree equality.

The first Android 16 boot completed in about 121 seconds, followed by a 30-second
stable monitor interval. The bounded basic device smoke check passed boot,
service, APEX, package, and crash-buffer gates. A synthetic input-event test
also passed the R8 SW_FLIP filter regression and cleaned up its virtual device.
Neither the synthetic test nor the basic smoke check qualifies physical cover
behavior or broad application use.

## Open issues

- **Deep-sleep Wi-Fi:** the short #13 screen-off poll does not establish deep
  sleep or overnight behavior. Kernel #15 passed bounded direct-scan and
  screen-off saved-network rejoin checks, including a 60-second USB-polled
  interval. Deep-sleep and overnight behavior remain unqualified; the cause of
  the earlier overnight disconnect remains unknown.
- **Audio routing:** the temporary candidate recovered ordinary headphone and
  speaker playback after two physical plug/unplug cycles. The cause has not been
  isolated. Owner confirmation of audio playback after the R8 boot remains
  pending, so the packaged fix is not yet runtime-qualified.
- **Book Cover Keyboard:** the owner confirmed Search worked in Chrome during an
  isolated keylayout trial. A keyboard reconnection later coincided with a
  system-server crash on Samsung `gpio_keys` switch code 21 (`SW_FLIP`). R8 adds
  a narrow EventHub filter and a common keylayout. A synthetic filter regression
  passed on R8. The owner later reported several reconnects and Chrome Search
  working; launcher Search remained inert. The a035 keylayout maps Lang to
  LANGUAGE_SWITCH. The owner reported Shift+2 produced a double quote and
  pressing Lang again restored @, though there is no clear visual indication.
  No synchronized IME subtype/KCM readback confirmed which layouts were active.
  A read-only snapshot after reconnect showed the selected System keylayout, the
  same boot/core identities as the synthetic test, and an empty crash buffer,
  but was not an event-aligned capture. The code-706 show/hide key and physical
  reconnect path remain unqualified.
- **Setup layout:** the Choose screen lock heading/subtitle can be clipped in
  Lineage onboarding. The ordinary Settings lock picker was observed without
  the clipping; the onboarding issue remains open.
- **Stutter and memory:** occasional app-switch jank and browser dropped frames
  remain. The measured available memory did not establish severe sustained
  exhaustion or a cause for the jank. The first R8 foreground batch was
  inconclusive because of fixture staging and inventory/APK-install failures.
  A later corrected run passed GLES2/3 drawing, ES3.1 compute, WebView
  JavaScript, and a speaker-route API check, which confirms sample acceptance
  rather than human audibility. R8 passed 32 decoder executions across 19
  generated cases and all nine additional moving 20-second AVC/HEVC clips at
  1080p60/4K30 and HEVC Main10. Both Qualcomm video encoders produced outputs
  with 30 frames each verified by independent host decode. The strict suite
  remains false because five expected legacy VC-1/DivX components are not
  advertised. These bounded fixtures do not qualify secure playback, DRM/HDR,
  sustained performance, paced 60 fps or every-frame hardware decode. Browser
  drop counters and callbacks have the same timing limits.
- **Camera quality/endurance:** colors, green-bar behavior, long sessions,
  repeated cold boots and wider third-party use remain unqualified. The original
  maintainer reported webcam color problems; do not assume they are fixed.
- **Android Linux Terminal:** unsupported. The port kernel does not enable
  `CONFIG_VIRTUALIZATION`; the Android Linux Terminal/Android Virtualization
  feature was not enabled or tested.
- Five expected legacy VC-1/DivX components remain unadvertised: four nonsecure
  and one secure. GPS fix, Widevine level, protected streaming, HDR output, USB
  OTG, powered-off charging and voice/video calls are not fully qualified.

## Google Apps and inherited limits

A clean R4 install plus MindTheGapps Android 16 ARM64 20260915 booted. The three
core Google APKs and add-on restoration script were checked against the separate
package before OTA. Some Google extras logged startup failures before the first
user unlock. After normal unlock on R8, bounded package/runtime, APEX, WebView,
process-stability and crash-indicator checks passed. The R8 dirty upgrade
retained the separate add-on without reinstalling it, and read-only post-install
checks matched all three core APKs and the add-on script. These checks do not
establish Google account setup, sign-in, Play Store certification/downloads, or
interactive Google Apps behavior. Google Apps are not included in the ROM ZIP.

SELinux is permissive, Data encryption is unsupported and Android Verified Boot
is disabled. Samsung/Qualcomm kernel and vendor components remain old; the
vendor security baseline is March 2020. R4 and R8 artifacts use development
signing. Tests cover one tablet and bounded sessions. A long-term public
signing-key choice and qualification of that exact signed artifact remain
release follow-ups. There is no SM-T825/LTE support claim.

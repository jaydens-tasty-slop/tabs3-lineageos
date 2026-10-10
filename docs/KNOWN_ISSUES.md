# Qualification and known issues

Device: SM-T820 (`gts3lwifi`). Framework: LineageOS 23.2 / Android 16.
Current signed candidate kernel: `3.18.140-jaydenmilne-tabs3-v1+`, #17.
Last reviewed: October 10, 2026 UTC. The historical R8 package below used kernel #15.

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

## Privately signed candidate

`23.2-20261010_003605-UNOFFICIAL-gts3lwifi` uses persistent private signing
keys and the standard `release-keys` tag. Offline checks verified 161 APK
certificates, 34 APEX container certificates/public keys and payload AVB
signatures, the whole-file OTA signature/trust, and the exact
source/System/Boot/OTA ADB cleanup gate. No embedded authorization keys or
forced ADB activation are included.

Its same-key dirty upgrade from the signed `140353` candidate completed
through TWRP CLI/GUI success barriers. Boot and both new HWUI libraries matched
the release, Recovery stayed unchanged, and the three separate GApps factory
APKs/add-on script survived with matching hashes. The exact ZIP booted in
110.6 seconds and passed a 35.491-second read-only build/kernel, secure
ordinary-ADB, Google core-package and core-process check. All 34 APEX modules
are active, and Wi-Fi has validated internet connectivity.

Settings profile-photo/default-icon updates on the previous signed ZIP failed
with `Could not copy bitmap to parcel blob`. Android's enabled memfd path asks
for `F_SEAL_FUTURE_WRITE`, which the 3.18 kernel rejects with EINVAL. Both ABIs
reproduced the failure above 12 KiB. The new HWUI capability check falls back to
protected ashmem and passed all ten roundtrips per ABI against the installed
libraries. A permission-free ordinary app also passed 10/10 cases. Settings →
Users now stays open and renders the profile icon; that same screen reproduced
the fatal exception on the baseline. The new source export contains 26 project
patches; the previous 25 patch hashes and kernel/Boot payload are unchanged.

The historical initial-clean-boot logs contain Google TTS and Digital
Wellbeing failures accessing credential-protected data before unlock. These
also predate private signing. No such fatal exception appeared during this
new dirty-upgrade boot or its focused checks. After normal unlock, Digital
Wellbeing rendered its dashboard and Google TTS initialized, listed 473 voices
and generated an 80,588-byte file with the installed offline en-US voice.
The diagnostic app/audio were removed; the final crash buffer was clear.
Initial clean-boot timing and wider Google Apps behavior remain unqualified.

The previous signed `140353` ZIP passed a clean TWRP installation with separate
MindTheGapps. This new ZIP's clean-install path remains unqualified. The old
sleep-study baseline was canceled before unplugging for crash troubleshooting.
A fresh overnight study on the exact current ZIP with separate GApps lasted
11 hours 48 minutes unplugged, battery 100% to 98%, with no intervening charge
or screen use until the tablet was picked up just before reconnecting USB.
Boot and core-process identities were unchanged and the crash buffer was empty.
Wi-Fi recorded one AP-initiated inactivity disassociation (reason 4), then
automatically rejoined the same saved network with the screen off: IP
configuration recovered in 683 ms and internet validation in 993 ms. The
earlier multi-hour outage was not reproduced; a single study does not establish
that the PNO changes caused this improvement.

Endpoint capture followed about 26 minutes of USB recharging. Retained battery
history supplies the real precharge readings; the raw endpoint was already
back at 100%. Kernel clocks measured 11 hours 39 minutes of suspend, or 95.1%
of their entire 12 hours 15 minutes bracket including USB. That percentage is
not the exact fraction of the unplugged interval. Kernel counters recorded
500 successful and 124 failed suspend attempts, no failed resumes, and 1,654
RPM vmin entries with about 11 hours 39 minutes accumulated in vmin. These
observations do not qualify every driver transition or the deepest power mode.

Historical hardware results are not transferred to this ZIP. Settings Build
number shows the platform ID without `test-keys`; the LineageOS version carries
the build date. Temporary USB stay-awake was restored to its original value.

The earlier `103849` cleanup build booted and passed bounded read-only secure
ADB/GApps/process checks. Further testing of that development-signed package
was canceled to prepare the privately signed replacement.

Double-tap-to-wake is disabled by inherited
`config_supportDoubleTapWake=false`. The shared touchscreen driver contains
some gesture support, but actual Tab S3 firmware support has not been established.

## Historical R8 package review

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

- **Deep-sleep Wi-Fi:** the current signed ZIP and #17 kernel passed one
  reviewed 11h48m unplugged overnight observation with separate GApps. A brief
  AP-initiated disconnect recovered automatically with the screen off; the
  older multi-hour outage was not reproduced. Its cause remains unknown, and
  one interval does not qualify all access points, longer standby or every
  suspend transition. The earlier #13/#15 USB-polled checks remain separate.
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
signing. Tests cover one tablet and bounded sessions. Persistent private signing keys
are in use; the current signed ZIP passed the scoped checks above. Its clean
installation remains pending; one scoped overnight observation passed. There
is no SM-T825/LTE support claim.

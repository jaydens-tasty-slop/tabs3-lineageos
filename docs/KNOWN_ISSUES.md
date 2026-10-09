# R4 qualification and R8 installation review

Device: SM-T820 (`gts3lwifi`). Framework: LineageOS 23.2 / Android 16.
Kernel: 3.18.140, with R8 carrying a new #15 image. Last reviewed: October 9,
2026.

## Tested R4 operations

| Area | Evidence and limits |
| --- | --- |
| Boot and installation | Exact R4 TWRP ZIP boots; installed System file contents and Boot match the package. Recovery was preserved. A separate clean R4 install plus MindTheGapps Android 16 ARM64 booted. The R8 dirty upgrade completed through TWRP command-line and GUI success barriers. Read-only checks then passed for 27 changed System content/module/metadata entries and the three separate Google core APKs/add-on script. Android 16 first boot completed in about 121 seconds and remained stable for a 30-second monitor interval. Basic boot/service/APEX/package/crash-buffer smoke passed. This is one bounded installation and boot, not broad application qualification. |
| Camera | Bounded R4+GApps review covered Camera2 full-size JPEGs on both cameras, Camera1 JPEGs, short AVC/HEVC video and two-cycle front/rear WebView camera streams. Colors, green-bar behavior, endurance and repeated cold boots remain open. |
| Wi-Fi | R4 enables, scans, connects, transfers LAN traffic with UID accounting, and reconnects while awake. A #13 kernel PNO/direct-scan and saved-network rejoin check passed in a short screen-off poll. R8 uses a distinct #15 kernel. Its Boot-only trial, with the R4 System unchanged, accepted a direct scheduled scan with capacity 16, one SSID and one match set; it stopped cleanly and preserved the existing connection. Android rejoined the same saved network with the display off in 1.1 seconds. Twelve USB-polled samples remained connected during a 60-second screen-off interval. This does not establish deep sleep or overnight behavior or explain the earlier overnight disconnect. |
| Video and browser | R4 checks covered moving decoder cases including H.264/HEVC 1080p60 and 4K30, HEVC Main10, and five hardware encoders with independent decoding. Chrome 154 passed a generated local JavaScript/WebGL fixture with Adreno 530. Separate generated 1080p60 clips reported 27 AVC and 6 HEVC dropped frames. Those counters do not establish paced 60 fps or prove every frame used hardware decode. |
| Audio | R4 PCM speaker, microphone and DSP playback checks passed. A temporary audio-policy runtime candidate preserved the primary speaker route across two physical headphone cycles; the owner confirmed website audio through headphones and speakers after unplug. R8's changed library passed exact post-install file checks, but owner playback after the R8 boot remains pending. |
| Graphics and input | R4 bounded GLES/Vulkan compute, sensor delivery and local WebView checks passed. The owner verified touch, buttons, haptics, S-Pen and flashlight. R8's synthetic SW_FLIP filter test passed with cleanup and stable core identities. The owner later reported multiple physical cover reconnects and Search working in Chrome, while launcher Search was inert and Lang had no visible effect. A read-only check confirmed the selected System keylayout. The reconnect capture was not event-aligned, so it does not prove that every physical transition followed the corrected path. The optional language action, launcher Search, and physical cover behavior remain partly unqualified. |
| Bluetooth and standby | Owner verified Bluetooth pairing. One unplugged overnight interval lasted about 12 h 19 min, battery 100% to 98%, approximately 98.8% kernel suspend, and no reboot. Wi-Fi was disconnected for about 4 h 53 min and rejoined when the display woke. |

## R8 offline package review

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
  working; launcher Search remained inert and Lang showed no visible effect. A
  read-only snapshot after reconnect showed the selected System keylayout, the
  same boot/core identities as the synthetic test, and an empty crash buffer,
  but was not an event-aligned capture. The code-706 show/hide key and physical
  reconnect path remain unqualified.
- **Setup layout:** the Choose screen lock heading/subtitle can be clipped in
  Lineage onboarding. The ordinary Settings lock picker was observed without
  the clipping; the onboarding issue remains open.
- **Stutter and memory:** occasional app-switch jank and browser dropped frames
  remain. The measured available memory did not establish severe sustained
  exhaustion or a cause for the jank. The first R8 foreground batch was
  inconclusive: the media fixture staging path did not match the validator,
  inventory timed out, and later APK installs failed. Its separate Vulkan child
  passed, but media decode, audio-route, WebView, and broader GPU checks did not
  run. The staging regex and install/inventory reporting have been updated, and
  a diagnostic APK was rebuilt; the correction has not been requalified.
- **Camera quality/endurance:** colors, green-bar behavior, long sessions,
  repeated cold boots and wider third-party use remain unqualified. The original
  maintainer reported webcam color problems; do not assume they are fixed.
- Four advertised legacy VC-1/DivX components remain unavailable. GPS fix,
  Widevine level, protected streaming, HDR output, USB OTG, powered-off charging
  and voice/video calls are not fully qualified.

## Google Apps and inherited limits

A clean R4 install plus MindTheGapps Android 16 ARM64 20260915 booted. The three
core Google APKs and add-on restoration script were checked against the separate
package before OTA. Speech Services and Digital Wellbeing had Direct Boot
failures before user unlock. Account setup, Play Store downloads/certification
and broad Google Apps compatibility remain unqualified. Google Apps are not
included in the ROM ZIP. The R8 dirty upgrade retained the separate add-on
without reinstalling it, and read-only post-install checks matched all three
core APKs and the add-on script. After normal unlock, bounded package/runtime
checks passed. They do not establish account setup, Play Store
certification/downloads, or interactive Google Apps behavior.

SELinux is permissive, Data encryption is unsupported and Android Verified Boot
is disabled. Samsung/Qualcomm kernel and vendor components remain old; the
vendor security baseline is March 2020. R4 and R8 artifacts use development
signing. Tests cover one tablet and bounded sessions. Final release signing and
qualification of a signed package remain pending. There is no SM-T825/LTE
support claim.

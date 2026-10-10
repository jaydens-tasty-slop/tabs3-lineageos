# Installing the experimental Tab S3 build

## Device and recovery

Use **Samsung Galaxy Tab S3 Wi-Fi SM-T820 (`gts3lwifi`)** and the original
maintainer's **TWRP 3.7.0_9-0 without encryption**. SM-T825/LTE and encrypted Data
are unsupported. The ROM ZIP writes Boot and System; Recovery and Samsung
firmware are retained.

The current privately signed candidate is
`lineage-23.2-20261010_003605-UNOFFICIAL-gts3lwifi.zip`, SHA-256:

```text
65aea8e4ea822238492021b7d3c8a33ba4ffbf68815a64d99b9a9b701b858172
```

All offline signing/image/ADB-cleanup audits passed. A same-key dirty upgrade
from the signed `140353` candidate completed, preserving separate MindTheGapps.
Boot and both new bitmap libraries matched the release; Recovery stayed
unchanged. The exact ZIP booted in about 111 seconds and passed a 35-second
secure ordinary-ADB/core-process check, bitmap regression, Settings → Users,
Digital Wellbeing and offline Google TTS checks. Its unplugged Wi-Fi/GApps
study remains deferred and requires a fresh baseline.

The prior signed `140353` candidate passed the clean-install sequence below
with separate MindTheGapps. The new ZIP's clean installation has not been
qualified. Historical R4/R8 results do not qualify this exact signed ZIP.

## Clean installation

This project uses a clean install for the transition from development keys to
the persistent private signing identity. App data and settings are cleared.
Back up personal files and recovery partitions, and verify a separate copy
before changing a tablet that contains data you want to retain.

1. Verify the ROM against the release checksum on your computer. Keep the ZIP
   on an external SD card accessible to TWRP. If Google Apps are wanted, also
   obtain an Android 16 ARM64 package separately and verify its checksum.
2. Boot to the specified TWRP and confirm SM-T820 and unencrypted Data.
3. Select **Wipe → Advanced Wipe → Data, Cache, System**. Leave Internal Storage
   and external storage unchecked. Confirm the wipe. The tested CLI sequence
   used a media-preserving Data wipe; the equivalent UI path is guidance, not a
   separately tested procedure. Do not rely on a wipe preserving personal files.
4. Select **Install**, choose the ROM ZIP, and confirm. Wait for success.
   The maintainer's new signing certificate is absent from this legacy TWRP's
   trust store; independently verify the checksum and leave TWRP's optional
   ZIP-signature verification unchecked for this install.
5. If wanted, flash the separate Google Apps ZIP now, before the first Android
   boot. The recorded add-on was
   `MindTheGapps-16.0.0-arm64-20260915_222150.zip`, SHA-256
   `d60f550e4dc96606644fbbf886a9892d1391a607225e861ceaef27bd999bc6a3`.
   Google Apps are optional and are not included in the ROM ZIP.
6. Reboot to System only after the installers succeed. Complete initial setup.
   USB debugging and host authorization must be enabled normally if wanted;
   no authorization keys or forced ADB activation are included.

If installation fails, retain the recovery message and logs for review before
performing further operations. Encrypted Data or migration from a different
Android version needs device-specific planning; the media-preserving reset
above does not qualify those migrations.

## Later updates

Keep the same persistent ROM signing identity. The signed `140353` → `003605`
dirty update completed through the TWRP CLI and GUI success barriers with no
Data wipe. The separately installed GApps factory packages and restoration
script matched their original hashes afterward; Android's updated Google
packages remained available. This qualifies that one update path. Flash the
ROM through TWRP, wait for installer success and then reboot; do not reinstall
or remove GApps during an ordinary same-key update without a specific reason.
Migration from older Android versions or development signing keys requires a
separately planned clean installation.

Google account setup, Play Store certification/downloads, and broad Google Apps
behavior remain unqualified. See [known issues](KNOWN_ISSUES.md),
[build instructions](BUILDING.md), and [signing](SIGNING.md).

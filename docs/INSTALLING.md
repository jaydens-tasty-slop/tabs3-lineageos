# Installing the experimental Tab S3 build

## Device and recovery

Use **Samsung Galaxy Tab S3 Wi-Fi SM-T820 (`gts3lwifi`)** and the original
maintainer's **TWRP 3.7.0_9-0 without encryption**. SM-T825/LTE and encrypted Data
are unsupported. The ROM ZIP writes Boot and System; Recovery and Samsung
firmware are retained.

The current privately signed candidate is
`lineage-23.2-20261009_140353-UNOFFICIAL-gts3lwifi.zip`, SHA-256:

```text
2faffdea5c7b9ad27a7e7149ac6ae37028aa0d48e0236bbbc19a26ae0aac3887
```

Its offline signature and source/image checks passed. A clean TWRP install
with separate MindTheGapps completed, including Boot image readback and
verification that Recovery was unchanged. The exact signed ZIP booted and passed
a bounded read-only build/kernel, secure ordinary-ADB, GApps core-package and
35-second core-process stability check. Its unplugged Wi-Fi/GApps study is
armed; overnight results remain pending.
Historical R4/R8 results do not qualify this exact signed ZIP.

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

Keep the same persistent ROM signing identity. A dirty update between two
privately signed releases has not yet been qualified. Earlier R8 preserved
GApps during a dirty upgrade from R4, but that historical development-key
upgrade does not establish this new release's upgrade behavior.

Google account setup, Play Store certification/downloads, and broad Google Apps
behavior remain unqualified. See [known issues](KNOWN_ISSUES.md),
[build instructions](BUILDING.md), and [signing](SIGNING.md).

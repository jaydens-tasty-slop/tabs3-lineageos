# Installing the Tab S3 release

## Device and recovery

Use **Samsung Galaxy Tab S3 Wi-Fi SM-T820 (`gts3lwifi`)** and the original
maintainer's **TWRP 3.7.0_9-0 without encryption**. encrypted Data
is unsupported. SM-T825/LTE (`gts3llte`) has a separate, untested build whose
ZIP name ends in `-UNTESTED.zip`; it may have no working modem. The ROM ZIP writes Boot and System; Recovery and Samsung
firmware are retained.

The final Android 17 package and checksum are not yet published. Do not install
an older development ZIP as though it were the final release. The final entry
will be added only after a clean public-buildroot reconstruction, package audit,
clean installation and runtime qualification. Android 16 results documented
elsewhere are historical and do not qualify Android 17.

## Clean installation

This project uses a clean install for the transition from development keys to
the persistent private signing identity. App data and settings are cleared.
Back up personal files and recovery partitions, and verify a separate copy
before changing a tablet that contains data you want to retain.

1. Verify the ROM against the build checksum on your computer. Keep the ZIP
   on an external SD card accessible to TWRP. If Google Apps are wanted, also
   obtain an Android 17 ARM64 package separately and verify its checksum.
2. Boot to the specified TWRP and confirm SM-T820 and unencrypted Data.
3. Select **Wipe → Advanced Wipe → Data, Cache, System**. Leave Internal Storage
   and external storage unchecked. Confirm the wipe. The tested CLI sequence
   used a media-preserving Data wipe; the equivalent UI path is guidance, not a
   separately tested procedure. Do not rely on a wipe preserving personal files.
4. Select **Install**, choose the ROM ZIP, and confirm. Wait for success.
   The build's signing certificate is absent from this legacy TWRP's
   trust store; independently verify the checksum and leave TWRP's optional
   ZIP-signature verification unchecked for this install.
5. If wanted, flash the official Android 17 ARM64 package tested with the
   candidate, `MindTheGapps-17.0.0-arm64-20261006_111038.zip`, now, before the
   first Android boot. Its SHA-256 is
   `6b38929ec345d96b6d64ad82f391869b7a60b3260efb0661b543b109b3ce646d`.
   Obtain it from the MindTheGapps GitHub release and verify the checksum;
   Google Apps are optional and are not included in the ROM ZIP. Do not flash
   the previously recorded Android 16 package.
6. Reboot to System only after the installers succeed. Complete initial setup.
   USB debugging and host authorization must be enabled normally if wanted;
   no authorization keys or forced ADB activation are included.

If installation fails, retain the recovery message and logs for review before
performing further operations. Encrypted Data or migration from a different
Android version needs device-specific planning; the media-preserving reset
above does not qualify those migrations.

## Later updates

Keep the same ROM signing identity for later builds. No Android 17 dirty-update
path has yet been qualified. Migration from Android 16, another Android major
version, or a different signing identity requires a clean installation.

Google account setup, Play Store downloads, and basic Google services have been
exercised on the candidate; certification and broad Google Apps behavior remain
unqualified. See [known issues](KNOWN_ISSUES.md),
[build instructions](BUILDING.md), and [signing](SIGNING.md).

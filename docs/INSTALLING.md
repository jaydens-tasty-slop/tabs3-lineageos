# Installing the experimental Tab S3 build

## Supported device and recovery

This build is for the Samsung Galaxy Tab S3 Wi-Fi **SM-T820** (`gts3lwifi`). It
is not for the SM-T825/LTE. Use the maintainer's TWRP **3.7.0_9-0 without
encryption** recovery build. Data encryption is unsupported. The ROM ZIP writes
Boot and System; it does not install Samsung firmware or replace Recovery.

Back up personal files and make a recovery backup before changing the ROM.
Copy the backup to separate storage and verify it there. Keep a copy of the ROM
ZIP and checksum file that can be reached from TWRP.

## R8 dirty upgrade

The instructions in this section describe the earlier tested R8 ZIP. The
replacement build `23.2-20261009_103849-UNOFFICIAL-gts3lwifi` passed the offline
ADB/source/OTA release gate, but has not been installed or booted. Do not treat
the earlier R8 upgrade result as qualification of that replacement build.

The tested R8 path upgraded the already installed HARDWARE-R4 Android 16 build
through TWRP 3.7.0_9-0. This does not qualify an upgrade from another Android
16 ROM, an older Android version, or a clean installation. A clean R8
installation has not been qualified. Do not use this section as a clean-install
or downgrade procedure.

1. Download the ROM ZIP and its `SHA256SUMS` file from the same release folder.
2. From a terminal in that folder, verify the bundle with
   `sha256sum -c SHA256SUMS`. Do not install a ZIP whose checksum fails.
3. Copy the ROM ZIP to the tablet or an accessible SD card, then boot the
   SM-T820 into the maintainer's TWRP 3.7.0_9-0 recovery. This tested path
   assumes the tablet already runs the tested HARDWARE-R4 Android 16 build and
   has the separate MindTheGapps add-on installed.
4. In TWRP, choose **Install**, select the exact ROM ZIP, and swipe to confirm.
   Wait for TWRP to report success. Do not choose **Install Image** or select a
   standalone `boot.img`.
5. Reboot to **System** and allow Android to complete startup. The first R8 boot
   completed in about two minutes on the tested tablet; timing can vary.

The successful R8 upgrade preserved the already installed separate Google Apps
add-on through the ROM's add-on restoration path. Do not flash Google Apps a
second time during this tested dirty-upgrade procedure. Google Apps are not
included in the ROM ZIP.

If TWRP reports an install failure, stop in recovery and retain the message for
review. Do not wipe Data, format storage, flash firmware, replace Recovery, or
reboot into a partially installed system as a troubleshooting step.

## Proposed clean installation and optional separate Google Apps

A clean R4 installation followed by a separate Android 16 ARM64 MindTheGapps
add-on before the first Android boot booted once. That historical R4 ZIP is not
included in this bundle. Its recorded recovery sequence wiped Data and Cache,
installed the ROM, then installed the GApps ZIP before booting Android. The Data
wipe was media-preserving: it cleared app and settings data while retaining
`/data/media`. Back up internal media anyway and verify a separate copy before
starting; do not rely on a wipe preserving personal files.

The following is a proposed TWRP UI procedure adapted to the included R8 ZIP
from that recorded R4 sequence. **A clean R8 install has not been tested.** The
TWRP UI sequence is also proposed, not separately tested:

1. Confirm the tablet is SM-T820 (`gts3lwifi`), Data is not encrypted, and the
   recovery is the maintainer's TWRP 3.7.0_9-0 without encryption build. Make
   verified backups of Boot, System, Data and Recovery, plus internal media;
   keep and verify a copy on separate storage. Keep the R8 ZIP, its checksum,
   and—if wanted—the separate GApps ZIP available from recovery. If Data is
   encrypted, stop and consult the maintainer's device-specific migration
   procedure. Do not choose **Format Data** blindly; it can erase internal
   media and staged files.
2. In TWRP choose **Wipe → Advanced Wipe**, select **Data** and **Cache**, and
   confirm the wipe. Leave **Internal Storage** and all external storage
   unchecked. Do not choose **Format Data**. This reflects the media-preserving
   Data wipe in the R4 record; it is not a promise that user files are safe.
3. Install the included R8 ROM ZIP and verify TWRP reports success. If Google
   Apps are wanted, install a separate Android 16 ARM64 GApps package in the
   same recovery session, before booting Android, and verify its success too.
   Google Apps are optional and are not baked into this ROM. Do not boot Android
   between the ROM and optional GApps installs.
4. Reboot to **System** only after the ROM install and any chosen GApps install
   complete. This proposed R8 clean path remains unqualified; the historical R4
   clean path booted once, which does not establish R8 clean-install behavior.

Do not use this proposed sequence to retain Data from another Android version.
If recovery, encryption state, backup verification or installer results differ
from these requirements, stop and review the device-specific recovery
procedure before proceeding.

Google account setup, Play Store certification and downloads, and broader
Google Apps behavior have not been qualified. The release does not include
Google Apps.

## Scope

The R8 package passed a dirty upgrade from the tested R4 Android 16 state and
targeted post-install checks on one SM-T820. This does not establish support
for other Tab S3 variants, encrypted Data, every clean-install state, or
long-term reliability. See
[known issues](KNOWN_ISSUES.md) and [build/source details](BUILDING.md).

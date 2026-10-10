# Source distribution

The canonical reconstruction uses `manifests/base-source-lock.xml` and
`patches/index.json`: **1,174 pinned base projects and 26 patch entries**.
Every patch carries a checksum and an exact upstream base. Setup fetches the
projects as Git clones through Android `repo`, verifies the patches, and
applies them. There are no Git submodules.

## Published forks

All four repositories are genuine GitHub forks of the corresponding
`awesometic` repository. Their default branch is `tabs3/lineage-23.2`.

| Android path | Repository | Published commit |
| --- | --- | --- |
| `device/samsung/gts3l-common` | [Device common](https://github.com/jaydens-tasty-slop/tabs3-android_device_samsung_gts3l-common) | `9f9bfcecba0c0c9a9018a5fae746f0f83f905555` |
| `device/samsung/gts3lwifi` | [Wi-Fi device](https://github.com/jaydens-tasty-slop/tabs3-android_device_samsung_gts3lwifi) | `efb09886713c80890457bcadb37bc8d186e5ff12` |
| `kernel/samsung/msm8996` | [Kernel](https://github.com/jaydens-tasty-slop/tabs3-android_kernel_samsung_msm8996) | `f355ebdfddf9f138e1b9161db034f4b913963d22` |
| `vendor/samsung` | [Vendor](https://github.com/jaydens-tasty-slop/tabs3-proprietary_vendor_samsung) | `f6a87c20eb410363d2fa0f9628b05d59169bfd00` |

The forks have descriptive port commits and preserve upstream authorship.
Our commits use `jaydens-tasty-slop` and
`325336397+jaydens-tasty-slop@users.noreply.github.com`. Correcting that Git
identity changed commit IDs without changing source trees or patch contents;
frozen ROM provenance retains the original IDs.

These four branches cover device, kernel and vendor changes. The remaining
Android framework, platform and build changes are in the complete patch set.
Use the pinned manifest and all 26 patches together when building this release;
four fork checkouts alone are insufficient.

The common-device fork removes the temporary forced-ADB rule. The kernel
identifies the maintained `jaydenmilne-tabs3-v1` release and carries the Wi-Fi
scheduled-scan changes. The framework patches include the legacy-kernel bitmap
Parcel fallback. A `system/sepolicy` patch carries the exact Wi-Fi property
context without requiring another fork.

## Maintainer publication helper

`bash scripts/publish_source_forks.sh` verifies the pinned branch tips, source
trees, patch checksums and commit identities, then creates missing GitHub fork
relationships and pushes through the configured SSH key. It refuses divergent
branches and never force-pushes. Use `--check-local` for checks without network
access or publication. Missing staging clones can be restored from the already
published branches. The helper requires GitHub CLI authentication as the owner
and `~/.ssh/jaydens-tasty-slop`; neither is needed to build the ROM.

## Licenses and private material

Patches preserve each upstream project's license. The vendor patch contains
inherited proprietary Samsung files and a modification to the existing audio
primary HAL binary. Those files retain their original distribution terms.

The public build root excludes Android clones/output, caches, backups, EFS and
identity partitions, private keys, screenshots, raw device logs, working
research and personal engineering notes. The instructions reconstruct sources
and builds without copying a maintainer's private workspace.

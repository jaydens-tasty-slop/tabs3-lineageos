# Source distribution

The complete source reconstruction uses `manifests/base-source-lock.xml` and
all 24 patches in `patches/index.json`. Base revisions and patch hashes are
pinned. The default bootstrap therefore works independently of source-fork
publication.

Four source branch tips are prepared for the `tabs3/lineage-23.2` branch. Their
repository URLs are listed for review; verify availability and branch hashes
before relying on them. The build-root's patch series is the reproducible source
path.

| Android path | Prepared repository | Prepared branch commit |
| --- | --- | --- |
| `device/samsung/gts3l-common` | [Device common](https://github.com/jaydens-tasty-slop/tabs3-android_device_samsung_gts3l-common) | `01639c14a44741ca621841ecd13e9e49df89d188` |
| `device/samsung/gts3lwifi` | [Wi-Fi device](https://github.com/jaydens-tasty-slop/tabs3-android_device_samsung_gts3lwifi) | `7be944f10b8667e8b223304fdb46415f1194b79f` |
| `kernel/samsung/msm8996` | [Kernel](https://github.com/jaydens-tasty-slop/tabs3-android_kernel_samsung_msm8996) | `07fc6642e946697492d57e78f821055c3eea0ac7` |
| `vendor/samsung` | [Vendor](https://github.com/jaydens-tasty-slop/tabs3-proprietary_vendor_samsung) | `b8ed0f096fd02a1e0c886ff5c7bb03326395049a` |

The common, kernel and vendor fork tips retain their R4 source trees. The Wi-Fi
device tip preserves its R4 port commit and adds one descriptive R5 audio-route
property commit. That commit's tree matches the updated Wi-Fi source patch; it
does not establish a full R5 ROM qualification. The other 20 changed Android
projects are versioned patches rather than forks.

`system/sepolicy` is one of those shared Android project patches. It carries the
exact boolean property context for the Wi-Fi product integration; it does not
require a separate public source fork. `patches/index.json` records the three
R5 source deltas: the Wi-Fi product patch and frameworks/av patch are updated,
and a system/sepolicy patch is added. The 1,174-project base lock is unchanged.

## Modified inherited audio binary

The vendor patch modifies the inherited proprietary
`gts3l-common/proprietary/vendor/lib/hw/audio.primary.msm8996.so`.
The extraction fixup changes its ELF dependencies to use `libprocessgroup` and
`libaudioprimary_shim`, then corrects `PT_PHDR` virtual/physical address fields.

| Version | Bytes | SHA-256 |
| --- | ---: | --- |
| Pinned base | 516,088 | `a382bdaa03425a3fcca0a54fa2539d1d3ad3264d3181169356f8775cf2e63e99` |
| Tested R4 | 543,221 | `461e06f90716bc10c9fdd32227a147c16bf0ef3d6e89b727f4622d3903bf122b` |

The vendor binary is not licensed as Apache-2.0 or BSD source by this repository.
Added audio source files retain their Linux Foundation BSD notices. The tracked
`libnetd_updatable.so.lsdump` update is a source ABI declaration needed for the
legacy policy exports, rather than an accidentally collected build artifact.

## Private workspace material

The outer repository intentionally excludes Android clones/output, caches,
backups, EFS and identity partitions, private keys, screenshots, raw device logs,
working research and personal engineering notes. The public instructions describe
reconstructing the source and builds, rather than copying a maintainer's workspace.

# Source distribution

The complete source reconstruction uses `manifests/base-source-lock.xml` and all
23 patches in `patches/index.json`. All base revisions and patch hashes are
pinned. The default bootstrap therefore works independently of fork publication.

Four source forks are prepared under `jaydens-tasty-slop`, with the common branch
`tabs3/lineage-23.2`. Publication is performed by the maintainer's publishing
script; availability must be confirmed before announcing these links.

| Android path | Fork | R4 port commit |
| --- | --- | --- |
| `device/samsung/gts3l-common` | [Device common](https://github.com/jaydens-tasty-slop/tabs3-android_device_samsung_gts3l-common) | `01639c14a44741ca621841ecd13e9e49df89d188` |
| `device/samsung/gts3lwifi` | [Wi-Fi device](https://github.com/jaydens-tasty-slop/tabs3-android_device_samsung_gts3lwifi) | `b43e5a9bff8e06ccd34ce8dbdffeb241bd093701` |
| `kernel/samsung/msm8996` | [Kernel](https://github.com/jaydens-tasty-slop/tabs3-android_kernel_samsung_msm8996) | `07fc6642e946697492d57e78f821055c3eea0ac7` |
| `vendor/samsung` | [Vendor](https://github.com/jaydens-tasty-slop/tabs3-proprietary_vendor_samsung) | `b8ed0f096fd02a1e0c886ff5c7bb03326395049a` |

Each fork preserves upstream history and adds one descriptive commit whose tree
matches the tested R4 source tree. Exploratory local commit history is not part
of those published branches. Other Android changes are patches rather than
nineteen additional forks.

The source lock includes the upstream repository for every Android project;
`patches/index.json` identifies all changed projects and their base revisions.
Patches include build/framework, graphics/media, networking and legacy hardware
compatibility changes. Their original source licenses remain applicable.

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

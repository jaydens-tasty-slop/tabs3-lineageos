# Source distribution

The build root reconstructs Android from `manifests/base-source-lock.xml` and
the 25 patch entries in `patches/index.json`. The 1,174 base project revisions
and patch hashes are pinned. The final R8 source export passed 25 patch
application/reversal checks. Seven project snapshots differ between frozen R4
and R8. The base lock is unchanged.

The build does not depend on public source forks. Android `repo` checks out the
pinned base projects, then the indexed patches reconstruct the port. The table
below records four prepared source-fork branch tips for convenience. Their
clean branch commits have been checked against the exact R8 project trees; the
commit IDs differ from the source snapshot heads because the forks preserve a
descriptive port history. They are not a substitute for the complete R8
manifest and patch pins. Confirm remote availability and exact branch heads
before relying on a link. Fork publication is separate from this source
snapshot.

| Android path | Prepared repository | Prepared branch commit |
| --- | --- | --- |
| `device/samsung/gts3l-common` | [Device common](https://github.com/jaydens-tasty-slop/tabs3-android_device_samsung_gts3l-common) | `30e5a4c8c24598c4e617cce8b6cdab1909a54226` |
| `device/samsung/gts3lwifi` | [Wi-Fi device](https://github.com/jaydens-tasty-slop/tabs3-android_device_samsung_gts3lwifi) | `7be944f10b8667e8b223304fdb46415f1194b79f` |
| `kernel/samsung/msm8996` | [Kernel](https://github.com/jaydens-tasty-slop/tabs3-android_kernel_samsung_msm8996) | `6267bd50cfaf18dbf113ebe6d5731c12065cbb7e` |
| `vendor/samsung` | [Vendor](https://github.com/jaydens-tasty-slop/tabs3-proprietary_vendor_samsung) | `b8ed0f096fd02a1e0c886ff5c7bb03326395049a` |

R8's seven-project source delta includes the common device and Wi-Fi product,
`frameworks/av`, `frameworks/native`, the Samsung kernel, `system/sepolicy` and
`vendor/lineage`. The actual package source revisions are recorded in
`artifacts/.../provenance.json` and reconstructed through `patches/index.json`.
The prepared fork table does not claim runtime qualification of those changes.

The `system/sepolicy` patch carries the exact bool property context for the
Wi-Fi product integration; a separate source fork is unnecessary. The indexed
patches preserve each upstream project's license. The vendor patch also carries
inherited proprietary Samsung files and changes the existing audio primary HAL
binary. Those binaries retain their original distribution terms and are not
claimed as open source here.

## Private workspace material

The public build root excludes Android clones/output, caches, backups, EFS and
identity partitions, private keys, screenshots, raw device logs, working
research and personal engineering notes. The instructions describe
reconstructing the source and build, not copying a maintainer's workspace.

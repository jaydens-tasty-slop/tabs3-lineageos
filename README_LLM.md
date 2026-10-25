## Build

This repository builds Android 17 for the Wi-Fi SM-T820 (`gts3lwifi`) and, as
a **lightly tested** extra, the LTE SM-T825 (`gts3llte`). Every build produces one
ZIP for each. A user has reported that the SM-T825 ZIP boots; its modem/RIL is
unverified and probably does not work. On a Linux host with Git, Make, rootless
Podman and several hundred GiB of free space:

```sh
git clone https://github.com/jaydens-tasty-slop/tabs3-lineageos.git lineage-os
cd lineage-os
make
```

`make` fetches the pinned LineageOS source revisions, applies the complete port
snapshot, and produces a TWRP-flashable ZIP per tablet under
`android/out/target/product/gts3lwifi/` and `.../gts3llte/`. Subsequent builds reuse the checkout,
output and compiler cache. Ordinary builds use development signing keys; private
release keys are not part of this repository.

The source snapshot currently contains 1,252 pinned base projects and 35 patch
entries. Exact patch checksums are recorded in `patches/index.json`; `make
source-check` verifies that every patch reconstructs the intended Git tree.
Builds are not expected to be byte-for-byte identical because timestamps,
signing and container package versions can differ.

See the [build guide](docs/BUILDING.md), [installation guide](docs/INSTALLING.md),
[qualification guide](docs/TESTING.md), [source map](docs/SOURCES.md), and
[test scope and known issues](docs/KNOWN_ISSUES.md).

## Release and source identity

The qualified maintainer-signed package is
`lineage-24.0-20261020_022959-UNOFFICIAL-gts3lwifi.zip` (1,075,641,477 bytes,
SHA-256 `db55fb69535f488398953c61015f70e25ae2e5d0916f3d64634f537dbe62bf1f`).
It was clean-installed with
`MindTheGapps-17.0.0-arm64-20261006_111038.zip` (SHA-256
`6b38929ec345d96b6d64ad82f391869b7a60b3260efb0661b543b109b3ce646d`)
and passed the public full qualification profile 13/13; browser-profile testing
was waived for this signing-only release after passing on the preceding build.

The device, product, kernel, and proprietary-vendor forks use the
`tabs3/lineage-24.0` branch under the `jaydens-tasty-slop` GitHub account; the
patch snapshot in this repository remains the canonical, pinned reconstruction
of the complete multi-repository tree. Release artifacts use a persistent
private maintainer identity, while public rebuilds use normal development keys
unless a builder supplies their own private signing keys.

## Installation and qualification

Use TWRP 3.7.0_9-0, disable its legacy ZIP-signature toggle, wipe Data, Cache,
and System, flash the ROM, then flash optional Android 17 GApps before the first
boot; keep "Update Lineage Recovery alongside the OS" disabled to preserve
TWRP. Run `make test-quick` for the bounded release gate, `make test-full` for
generated media/camera/network/stability coverage, and `make test-browser` for
the ordinary-app browser/GPU profile; every run writes JSON and JUnit evidence
under the ignored `diagnostics/` directory.

This port intentionally retains major legacy-device limitations: SELinux is
permissive, userdata encryption and AVB are disabled, the vendor security
baseline is March 2020, and the release supports only the Wi-Fi SM-T820.

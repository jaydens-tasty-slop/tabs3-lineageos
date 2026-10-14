> **COGNITOHAZARD WARNING:** This README was witten by a real-life human being,
> but this project is otherwise 100% vibecoded and has not been graced by human
> eyes

# Entirely Vibecoded LineageOS 24.0 (Android 17) for the Samsung Galaxy Tab S3

The real credit goes to [awesometic](https://github.com/awesometic) for having a
kernel that brought this device to LineageOS 21. They did the bulk of the work,
this project just brings it over the finish line for LineageOS 24.0.

My contribution was pointing a robot at their work, telling it to get it on latest
android, and being its meat puppet

I've discovered it is quite delightful to funnel investor money to pointless
endeavors via heavily subsidized casino-esque subscriptions. It's like VC for
pointless side projects. Thanks, AI bubble!

## Build

This repository builds Android 17 for the Wi-Fi SM-T820 (`gts3lwifi`). The
SM-T825/LTE model is not supported. On a Linux host with Git, Make, rootless
Podman and several hundred GiB of free space:

```sh
git clone https://github.com/jaydens-tasty-slop/tabs3-lineageos.git lineage-os
cd lineage-os
make
```

`make` fetches the pinned LineageOS source revisions, applies the complete port
snapshot, and produces a TWRP-flashable ZIP under
`android/out/target/product/gts3lwifi/`. Subsequent builds reuse the checkout,
output and compiler cache. Ordinary builds use development signing keys; private
release keys are not part of this repository.

The source snapshot currently contains 1,251 pinned base projects and 34 patch
entries. Exact patch checksums are recorded in `patches/index.json`; `make
source-check` verifies that every patch reconstructs the intended Git tree.
Builds are not expected to be byte-for-byte identical because timestamps,
signing and container package versions can differ.

See the [build guide](docs/BUILDING.md), [installation guide](docs/INSTALLING.md),
[source map](docs/SOURCES.md), and [test scope and known issues](docs/KNOWN_ISSUES.md).

## Current status

The Android 17 port is undergoing final clean-build and installation
qualification. Do not treat an older development ZIP or the historical Android
16 branch as the final Android 17 release.

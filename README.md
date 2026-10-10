# LineageOS 23.2 for Samsung Galaxy Tab S3

Build **Android 16 for the Wi-Fi SM-T820 (`gts3lwifi`)** in Podman. This
unofficial port builds on awesometic's Tab S3 device, kernel and vendor work.
SM-T825/LTE is unsupported by this release.

## Build

On Linux, install Git, Make and rootless Podman, then:

```sh
git clone https://github.com/jaydens-tasty-slop/tabs3-lineageos.git lineage-os
cd lineage-os
make
```

`make` prepares the container image, fetches the pinned sources when the
checkout is absent, applies the port, and builds a TWRP-flashable ZIP. Android
build dependencies live in the container. Later runs reuse the checkout,
`android/out` and `state/ccache`; no clean is performed. Allow several hundred
GiB of storage on a Linux filesystem. See [the build guide](docs/BUILDING.md)
for the resource profile, interrupted fetches and incremental builds.

Output is under `android/out/target/product/gts3lwifi/lineage-*.zip`, with a
checksum alongside it. Ordinary builds use development signing keys; the
maintainer's private release keys are excluded. See [signing](docs/SIGNING.md)
before distributing your own build.

Useful targets:

```sh
make help           # All targets
make status         # Build container status
make logs           # Follow build output
make source-check   # Check the source patch snapshot without building
make smoke          # Read-only checks on an authorized USB-connected tablet
```

## Release

The qualified release artifact is:

```text
lineage-23.2-20261010_003605-UNOFFICIAL-gts3lwifi.zip
SHA256: 65aea8e4ea822238492021b7d3c8a33ba4ffbf68815a64d99b9a9b701b858172
```

It uses persistent private `jaydenmilne` signing keys, the Android
`release-keys` tag and kernel `3.18.140-jaydenmilne-tabs3-v1+`, #17. Install
through the original maintainer's **TWRP 3.7.0_9-0 without encryption**.
Google Apps are optional and must be flashed separately. USB debugging and
computer authorization are enabled normally by the owner; the release embeds
no host ADB keys or forced ADB activation.

This exact ZIP passed signing and image audits, a same-key TWRP update, boot,
bitmap regression, Settings/Digital Wellbeing and offline Google TTS checks.
An unplugged observation with separate GApps lasted **11h48m, battery 100%
to 98%**. A brief Wi-Fi disconnect recovered automatically with the screen
off in about one second. There was no recorded reboot or fatal crash.

The prior signed build passed a clean installation; a clean installation of
this exact ZIP has not been tested. Earlier builds received broader hardware
and media checks. These results cover one tablet and bounded sessions. See
[installation](docs/INSTALLING.md) and [test scope and known issues](docs/KNOWN_ISSUES.md).

SELinux is permissive, Data encryption is unsupported and Verified Boot is
disabled. Occasional stutter, the onboarding lock-screen layout and camera
quality/endurance remain open. Double-tap-to-wake and Android Linux Terminal
are unavailable. The kernel and proprietary vendor components remain old.

## Sources

Android **`repo` + a pinned manifest + 26 versioned patches** reconstruct the
complete port across 1,174 base projects. No Git submodules are needed. Four
published GitHub forks preserve upstream ancestry and the device, kernel and
vendor changes; see [the source map](docs/SOURCES.md).

The outer repository contains build setup, patches, documentation and portable
smoke tools. Source clones, build output, caches, keys, device logs, backups
and private progress notes stay outside Git. Rebuilding does not promise an
identical ZIP hash: build times, signing and container packages can differ.
A second build from a fresh checkout has not been run to qualify reconstruction.

## Credits and licenses

Thanks to awesometic, LineageOS, AOSP, Samsung, Qualcomm and other upstream
contributors. [Original Tab S3 ROM thread](https://xdaforums.com/t/rom-unofficial-14-eas-ota-sm-t820-sm-t825-2024-3-9-lineageos-21-for-galaxy-tab-s3.4660924/).

Build orchestration and documentation are Apache-2.0. Patched upstream code
retains its licenses; the kernel is GPLv2 and vendor binaries retain their
existing distribution terms. See [NOTICE](NOTICE).

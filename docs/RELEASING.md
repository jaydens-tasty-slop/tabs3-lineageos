# Release checklist

Maintainer steps for publishing a ROM release. Signing details are in
[SIGNING.md](SIGNING.md); installation text is in [INSTALLING.md](INSTALLING.md).
Never put private keys, the key-backup passphrase or device ADB keys in Git, in
release notes or in any uploaded file.

## 1. Sources

- [ ] Commit work in the fork checkouts that have a `publish` remote
      (`device/samsung/gts3l-common`, `gts3lwifi`, `gts3llte`,
      `kernel/samsung/msm8996`, `vendor/samsung`) on `tabs3/lineage-24.0`.
      Use the `jaydens-tasty-slop` identity and descriptive messages.
- [ ] Changes to every other project live only as patches. Run
      `python3 scripts/export_port.py` then `python3 scripts/verify_source_export.py`
      **inside the build container** (the verifier needs the Android checkout
      and LFS). Both must pass.
- [ ] Copy the regenerated `patches/*.patch` and `patches/index.json` into the
      public build root. Do not copy docs or other files wholesale: the
      working copy's docs can be older than the public ones.
- [ ] Update `docs/KNOWN_ISSUES.md`, `docs/INSTALLING.md` and the README if the
      change alters behavior, scope or tested claims.
- [ ] Commit and push the build root (`main`), then push each fork. Never
      force-push. Confirm each fork's published tip matches the local tip
      with `git ls-remote publish refs/heads/tabs3/lineage-24.0`.

## 2. Build

- [ ] Build `target-files-package` for **each** device (`gts3lwifi`, `gts3llte`;
      select with `TAB_S3_DEVICE`) inside the container with the source,
      patches and ccache mounted. Limit CPUs (`--cpus`, `nice`) on a shared
      machine. Check the build exit status, not only the log tail.
- [ ] Confirm the change is in the output (for example `grep` the built
      `init` script, or the symbol in `services.jar`).

## 3. Sign

- [ ] Run the signing script **inside the container**. Run on the host it can
      exit silently part way through.
- [ ] Use a new, unused signing output directory per release and device; the
      scripts refuse to overwrite one.
- [ ] Run the offline audit for each ZIP: APK and APEX certificates, OTA
      signature, `release-keys`, and the ADB properties audit. It must pass.
- [ ] The OTA signer certificate SHA-256 must equal the previous release's,
      otherwise users need a clean install; say so in the notes if it changes.

## 4. Test on a tablet

- [ ] Install the exact signed ZIP through TWRP (verify its SHA-256 on the
      device first). Prefer a same-key update; wipe `/data` by hand and keep
      `/data/media` when a factory reset is wanted, since `twrp wipe data`
      can hang.
- [ ] Exercise the changed behavior and a basic regression pass (boot, touch,
      Wi-Fi, brightness, navigation, USB storage). Record which model was
      tested. Anything not run on hardware must say so in the notes.

## 5. Publish

- [ ] Write `<zip>.sha256sum` for each ZIP.
- [ ] Create a GitHub release in `jaydens-tasty-slop/tabs3-lineageos`. Tag
      `lineage-24.0-<build timestamp of the Wi-Fi ZIP>`; attach both ZIPs and
      both checksum files.
- [ ] Notes include: summary of fixes, per-ZIP SHA-256, signer certificate
      hash, a **Testing** section stating exactly what was and was not run on
      hardware (LTE modem status in particular), changes since the last
      release, and known issues.
- [ ] Download an asset and recheck its SHA-256 against the notes.
- [ ] Delete temporary ZIPs from the tablet and keep the signed target files
      and signing logs under `state/`.

## 6. Keys

- [ ] Encrypted key backup exists and was round-trip verified. An off-machine
      copy is still the maintainer's responsibility; do not print or paste the
      passphrase.

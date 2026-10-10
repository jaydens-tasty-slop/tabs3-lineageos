# ROM signing

`make build` and `make package` produce development-signed build output. Public
ROMs use private APK, APEX container, APEX payload and OTA keys. A ZIP signature
alone does not replace the package signatures inside the ROM.

The maintainer's current release uses a persistent private `jaydenmilne`
identity and the standard Android `release-keys` build tag. Private keys are
kept outside Git in `state/release-signing/`, excluded from the container build
context, and backed up in an encrypted archive. The passphrase is stored
separately. Reuse the same keys for subsequent updates.

To distribute an independently signed build, follow the upstream
[AOSP release signing instructions](https://source.android.com/docs/core/ota/sign_builds)
using the host tools compiled inside Podman:

1. Build `target-files-package` from the pinned source snapshot.
2. Generate your own persistent APK certificates and APEX signing keys. Inspect
   `META/apkcerts.txt` and `META/apexkeys.txt` in the actual target-files ZIP to
   obtain the required signing roles; map module APK certificates too. This
   release required 53 distinct key pairs, including 34 APEX identities.
3. Run `sign_target_files_apks` with the APK certificate mappings, APEX
   container mappings and APEX payload keys, and `-o` to replace OTA trust.
   Preserve explicitly presigned APKs, including the CTS shim packages.
4. Run `ota_from_target_files --block --backup=true` using the signed target
   files and your OTA release certificate.
5. Verify actual APK and APEX container certificate fingerprints, APEX payload
   public keys and AVB signatures, whole-file OTA signature, and installed OTA
   trust. Run the source/System/Boot/OTA ADB audit on the signed outputs too.

Changing signing identity requires a clean install. Google Apps remain a
separate recovery add-on. The signing key does not establish TWRP trust: this
legacy recovery does not contain the maintainer's new certificate. Verify the
release checksum independently before installation.

Do not commit private keys, passphrases, key backups or device authorization
keys. A builder should generate their own identity; the maintainer's private
keys are not distributed with the sources.

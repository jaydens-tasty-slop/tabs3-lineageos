#!/usr/bin/env python3
"""Build separate ordinary Camera2 lifecycle controls with cloned SDK tools."""
import json
import pathlib
import subprocess
import tempfile
import zipfile
from build_validation_payloads import ROOT, TOOLS, JAR, D8, SIGNER, run, digest, archive_payload


def main():
    output = ROOT / "artifacts/device-camera-controls"
    output.mkdir(parents=True, exist_ok=True)
    archive_payload(output)
    sources = sorted((ROOT / "device-validation/camera-controls/src").rglob("*.java"))
    key = ROOT / "state/device-validation.keystore"
    with tempfile.TemporaryDirectory(prefix="camera-controls-apk-", dir=ROOT / "state") as temporary:
        directory = pathlib.Path(temporary)
        classes, dex = directory / "classes", directory / "dex"
        classes.mkdir()
        dex.mkdir()
        run("javac", "-source", "8", "-target", "8", "-bootclasspath",
            str(JAR) + ":" + str(TOOLS / "core-lambda-stubs.jar"), "-d", classes, *sources)
        run(*D8, "--min-api", "31", "--lib", JAR, "--output", dex, *sorted(classes.rglob("*.class")))
        manifest = directory / "AndroidManifest.xml"
        manifest.write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android"
            package="org.tabs3.validation.cameracontrols" android:versionCode="1" android:versionName="1.0">
          <uses-sdk android:minSdkVersion="31" android:targetSdkVersion="36"/>
          <uses-permission android:name="android.permission.CAMERA"/>
          <application android:label="Tab S3 Camera2 control" android:allowBackup="false"
              android:debuggable="true" android:theme="@android:style/Theme.Material.Light.NoActionBar">
            <activity android:name="org.tabs3.validation.cameracontrols.MainActivity" android:exported="true">
              <intent-filter><action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/></intent-filter>
            </activity>
          </application></manifest>''')
        unsigned, aligned = directory / "unsigned.apk", directory / "aligned.apk"
        apk = output / "tabs3-camera-controls.apk"
        run(TOOLS / "aapt2", "link", "-I", JAR, "--manifest", manifest, "-o", unsigned)
        with zipfile.ZipFile(unsigned, "a", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(dex / "classes.dex", "classes.dex")
        run(TOOLS / "zipalign", "-f", "4", unsigned, aligned)
        run(*SIGNER, "sign", "--ks", key, "--ks-key-alias", "validation",
            "--ks-pass", "pass:tabs3-diagnostics", "--key-pass", "pass:tabs3-diagnostics",
            "--out", apk, aligned)
        signature = subprocess.check_output([str(item) for item in [*SIGNER, "verify", "--verbose", "--print-certs", apk]], text=True)
        permissions = subprocess.check_output([str(TOOLS / "aapt2"), "dump", "permissions", str(apk)], text=True)
        requested = [line.strip() for line in permissions.splitlines() if line.strip().startswith("uses-permission:")]
        if len(requested) != 1 or "android.permission.CAMERA" not in requested[0]:
            raise ValueError("Camera controls must request only the ordinary CAMERA permission")
        (output / "signature.txt").write_text(signature)
        (output / "permissions.txt").write_text(permissions)
        (output / "build.json").write_text(json.dumps({
            "apk_sha256": digest(apk), "sdk": 36,
            "sources": {str(source.relative_to(ROOT)): digest(source) for source in sources},
            "package": "org.tabs3.validation.cameracontrols",
            "scope": "Normal SDK Camera2 preview/JPEG and direct/drained close; no photographs saved, native controls or ROM modifications",
            "run_on_tablet": False
        }, indent=2) + "\n")
        (output / "SHA256SUMS").write_text(digest(apk) + "  " + apk.name + "\n")
    archive_payload(output)
    print("Built separate ordinary Camera2 lifecycle controls: " + str(apk), flush=True)


if __name__ == "__main__":
    main()

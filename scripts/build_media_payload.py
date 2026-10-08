#!/usr/bin/env python3
"""Build the ordinary media/GPU APK offline using the cloned Android 36 SDK."""
import hashlib
import json
import pathlib
import subprocess
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS = ROOT / "android/prebuilts/sdk/tools/linux/bin"
JAR = ROOT / "android/prebuilts/sdk/36/public/android.jar"
# Throwaway password for this ignored diagnostic-only keystore; never use it for ROM/release signing.
DIAGNOSTIC_KEY_PASSWORD = "tabs3-diagnostics"
D8 = ["java", "-Xmx512m", "-cp", TOOLS.parent / "lib/d8.jar", "com.android.tools.r8.D8"]
SIGNER = ["java", "-Xmx256m", "-jar", TOOLS.parent / "lib/apksigner.jar"]


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = ROOT / "artifacts/device-media-validation"
    output.mkdir(parents=True, exist_ok=True)
    key = ROOT / "state/device-smoke-media.keystore"
    if key.is_symlink():
        raise ValueError("Refusing to use a linked smoke signing key")
    if not key.is_file():
        subprocess.run(["keytool", "-genkeypair", "-keystore", str(key), "-alias", "validation",
                        "-keyalg", "RSA", "-keysize", "2048", "-validity", "3650",
                        "-storepass", DIAGNOSTIC_KEY_PASSWORD, "-keypass", DIAGNOSTIC_KEY_PASSWORD,
                        "-dname", "CN=Tab S3 media diagnostic"], check=True)
        key.chmod(0o600)
    else:
        key.chmod(0o600)
    sources = sorted((ROOT / "device-validation/media/src").rglob("*.java"))
    with tempfile.TemporaryDirectory(prefix="media-apk-", dir=ROOT / "state") as temp:
        directory = pathlib.Path(temp)
        classes, dex = directory / "classes", directory / "dex"
        classes.mkdir(); dex.mkdir()
        run("javac", "-source", "8", "-target", "8", "-bootclasspath",
            str(JAR) + ":" + str(TOOLS / "core-lambda-stubs.jar"), "-d", classes, *sources)
        run(*D8, "--min-api", "29", "--lib", JAR, "--output", dex, *sorted(classes.rglob("*.class")))
        manifest = directory / "AndroidManifest.xml"
        manifest.write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android"
            package="org.tabs3.validation.media" android:versionCode="1" android:versionName="1.0">
          <uses-sdk android:minSdkVersion="29" android:targetSdkVersion="36"/>
          <application android:label="Tab S3 media and GPU probe" android:allowBackup="false"
              android:debuggable="true" android:theme="@android:style/Theme.Material.Light.NoActionBar">
            <activity android:name="org.tabs3.validation.media.MainActivity" android:exported="true">
              <intent-filter><action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/></intent-filter>
            </activity>
          </application>
        </manifest>''')
        unsigned, aligned, apk = directory / "unsigned.apk", directory / "aligned.apk", output / "tabs3-media-probe.apk"
        run(TOOLS / "aapt2", "link", "-I", JAR, "--manifest", manifest, "-o", unsigned)
        with zipfile.ZipFile(unsigned, "a", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(dex / "classes.dex", "classes.dex")
        run(TOOLS / "zipalign", "-f", "4", unsigned, aligned)
        run(*SIGNER, "sign", "--ks", key, "--ks-key-alias", "validation",
            "--ks-pass", "pass:" + DIAGNOSTIC_KEY_PASSWORD,
            "--key-pass", "pass:" + DIAGNOSTIC_KEY_PASSWORD, "--out", apk, aligned)
        verified = subprocess.check_output([str(x) for x in [*SIGNER, "verify", "--verbose", "--print-certs", apk]], text=True)
        (output / "signature.txt").write_text(verified)
        permissions = subprocess.check_output([str(TOOLS / "aapt2"), "dump", "permissions", str(apk)], text=True)
        if "uses-permission:" in permissions:
            raise ValueError("Media diagnostic must not request permissions")
        (output / "permissions.txt").write_text(permissions)
        (output / "build.json").write_text(json.dumps({
            "sdk": 36, "apk_sha256": digest(apk), "sources": {str(p.relative_to(ROOT)): digest(p) for p in sources},
            "android_jar_sha256": digest(JAR), "tool_jars": {p.name: digest(p) for p in (TOOLS.parent / "lib/d8.jar", TOOLS.parent / "lib/apksigner.jar")},
            "tools": {name: digest(TOOLS / name) for name in ("aapt2", "d8", "zipalign", "apksigner")},
            "builder_sha256": digest(pathlib.Path(__file__)),
            "scope": "Ordinary signed app, no permissions, debuggable only to retrieve its own JSON reports",
            "hardware_tested": False}, indent=2) + "\n")
        (output / "SHA256SUMS").write_text(digest(apk) + "  " + apk.name + "\n")
    print("Built and verified media diagnostic: " + str(apk), flush=True)


if __name__ == "__main__":
    main()

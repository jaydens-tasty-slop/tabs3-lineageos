#!/usr/bin/env python3
"""Build ordinary diagnostic APKs offline with pinned SDK tools in Podman."""
import hashlib
import json
import pathlib
import shutil
import subprocess
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS = ROOT / "android/prebuilts/sdk/tools/linux/bin"
JAR = ROOT / "android/prebuilts/sdk/36/public/android.jar"
D8 = ["java", "-Xmx512m", "-cp", TOOLS.parent / "lib/d8.jar", "com.android.tools.r8.D8"]
SIGNER = ["java", "-Xmx256m", "-jar", TOOLS.parent / "lib/apksigner.jar"]
OUTPUT = ROOT / "artifacts/device-validation"


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive_payload(output):
    """Preserve diagnostic APK/build bytes before another local iteration."""
    record = output / "build.json"
    if not record.is_file():
        return
    build = json.loads(record.read_text())
    candidates = list(output.glob("*.apk"))
    if "apk_sha256" not in build or len(candidates) != 1:
        raise ValueError("Expected one media or I/O diagnostic APK")
    apk = candidates[0]
    if digest(apk) != build["apk_sha256"]:
        raise ValueError("Diagnostic APK differs from its build record")
    target = ROOT / "artifacts/device-validation-versions" / build["apk_sha256"]
    target.mkdir(parents=True, exist_ok=True)
    for source in (apk, record, output / "signature.txt", output / "permissions.txt", output / "SHA256SUMS"):
        if source.is_file():
            destination = target / source.name
            if destination.exists() and destination.read_bytes() != source.read_bytes():
                raise ValueError("Immutable diagnostic record differs: " + str(destination))
            if not destination.exists():
                shutil.copyfile(source, destination)
    # An older APK can be preserved even if source edits have already started.
    # Copy only source bytes that actually match the saved build record.
    for relative, expected in build["sources"].items():
        source = ROOT / relative
        if source.is_file() and digest(source) == expected:
            destination = target / "sources" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and digest(destination) != expected:
                raise ValueError("Immutable diagnostic source differs")
            if not destination.exists():
                shutil.copyfile(source, destination)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    key = ROOT / "state/device-validation.keystore"
    if not key.exists():
        run("keytool", "-genkeypair", "-keystore", key, "-alias", "validation", "-keyalg", "RSA",
            "-keysize", "2048", "-validity", "3650", "-storepass", "tabs3-diagnostics",
            "-keypass", "tabs3-diagnostics", "-dname", "CN=Tab S3 ordinary diagnostic app")
        key.chmod(0o600)
    sources = sorted((ROOT / "device-validation/src").rglob("*.java"))
    report = {"hardware_tested": False, "scope": "Ordinary separately signed APKs; no platform/root permissions",
              "sdk": 36, "sources": {str(p.relative_to(ROOT)): digest(p) for p in sources},
              "tools": {name: digest(TOOLS / name) for name in ("aapt2", "d8", "zipalign", "apksigner")},
              "tool_jars": {name: digest(TOOLS.parent / "lib" / name) for name in ("d8.jar", "apksigner.jar")},
              "core_lambda_stubs_sha256": digest(TOOLS / "core-lambda-stubs.jar"),
              "android_jar_sha256": digest(JAR), "apks": []}
    with tempfile.TemporaryDirectory(prefix="validation-apks-", dir=ROOT / "state") as temporary:
        directory = pathlib.Path(temporary)
        classes, dex = directory / "classes", directory / "dex"
        classes.mkdir(); dex.mkdir()
        run("javac", "-source", "8", "-target", "8", "-bootclasspath",
            str(JAR) + ":" + str(TOOLS / "core-lambda-stubs.jar"), "-d", classes, *sources)
        run(*D8, "--min-api", "28", "--lib", JAR, "--output", dex,
            *sorted(classes.rglob("*.class")))
        for variant, internet in (("net", True), ("noinet", False)):
            package = "org.tabs3.validation." + variant
            manifest = directory / (variant + ".xml")
            manifest.write_text(f'''<manifest xmlns:android="http://schemas.android.com/apk/res/android"
                package="{package}" android:versionCode="1" android:versionName="1.0">
              <uses-sdk android:minSdkVersion="28" android:targetSdkVersion="36"/>
              {('<uses-permission android:name="android.permission.INTERNET"/>' if internet else '')}
              <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
              <uses-permission android:name="android.permission.VIBRATE"/>
              <application android:label="Tab S3 probe {variant}" android:allowBackup="false"
                  android:usesCleartextTraffic="true" android:theme="@android:style/Theme.Material.Light.NoActionBar">
                <activity android:name="org.tabs3.validation.MainActivity" android:exported="true">
                  <intent-filter><action android:name="android.intent.action.MAIN"/>
                    <category android:name="android.intent.category.LAUNCHER"/></intent-filter>
                </activity>
                <receiver android:name="org.tabs3.validation.ProbeReceiver" android:exported="true"/>
              </application>
            </manifest>''')
            unsigned, aligned = directory / (variant + "-unsigned.apk"), directory / (variant + "-aligned.apk")
            run(TOOLS / "aapt2", "link", "-I", JAR, "--manifest", manifest, "-o", unsigned)
            with zipfile.ZipFile(unsigned, "a", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(dex / "classes.dex", "classes.dex")
            run(TOOLS / "zipalign", "-f", "4", unsigned, aligned)
            output = OUTPUT / ("tabs3-probe-" + variant + ".apk")
            run(*SIGNER, "sign", "--ks", key, "--ks-key-alias", "validation",
                "--ks-pass", "pass:tabs3-diagnostics", "--key-pass", "pass:tabs3-diagnostics",
                "--out", output, aligned)
            run(*SIGNER, "verify", "--verbose", "--print-certs", output)
            permissions = subprocess.check_output([str(TOOLS / "aapt2"), "dump", "permissions", str(output)], text=True)
            if ("android.permission.INTERNET" in permissions) != internet:
                raise ValueError("APK permissions differ from the requested variant")
            (OUTPUT / (variant + "-permissions.txt")).write_text(permissions)
            report["apks"].append({"file": output.name, "package": package,
                                   "internet_permission": internet, "sha256": digest(output)})
    (OUTPUT / "build.json").write_text(json.dumps(report, indent=2) + "\n")
    (OUTPUT / "SHA256SUMS").write_text("".join(item["sha256"] + "  " + item["file"] + "\n"
                                              for item in report["apks"]))
    print("Built and signature/permission checked both diagnostic APKs: " + str(OUTPUT))


if __name__ == "__main__":
    main()

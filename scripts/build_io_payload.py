#!/usr/bin/env python3
"""Build the ordinary camera/sensor/microphone diagnostic with pinned SDK tools."""
import json
import pathlib
import subprocess
import tempfile
import zipfile
from build_validation_payloads import ROOT, TOOLS, JAR, D8, SIGNER, run, digest, archive_payload


def main():
    output = ROOT / "artifacts/device-io-validation"
    output.mkdir(parents=True, exist_ok=True)
    archive_payload(output)
    key = ROOT / "state/device-validation.keystore"
    sources = sorted((ROOT / "device-validation/io/src").rglob("*.java"))
    with tempfile.TemporaryDirectory(prefix="io-apk-", dir=ROOT / "state") as temp:
        directory = pathlib.Path(temp); classes, dex = directory / "classes", directory / "dex"
        classes.mkdir(); dex.mkdir()
        run("javac", "-source", "8", "-target", "8", "-bootclasspath", str(JAR)+":"+str(TOOLS / "core-lambda-stubs.jar"), "-d", classes, *sources)
        run(*D8, "--min-api", "31", "--lib", JAR, "--output", dex, *sorted(classes.rglob("*.class")))
        manifest = directory / "AndroidManifest.xml"
        manifest.write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android"
            package="org.tabs3.validation.io" android:versionCode="1" android:versionName="1.0">
          <uses-sdk android:minSdkVersion="31" android:targetSdkVersion="36"/>
          <uses-permission android:name="android.permission.CAMERA"/>
          <uses-permission android:name="android.permission.RECORD_AUDIO"/>
          <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS"/>
          <application android:label="Tab S3 I/O probe" android:allowBackup="false" android:debuggable="true"
              android:theme="@android:style/Theme.Material.Light.NoActionBar">
            <activity android:name="org.tabs3.validation.io.MainActivity" android:exported="true">
              <intent-filter><action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/></intent-filter>
            </activity>
          </application></manifest>''')
        unsigned, aligned, apk = directory / "unsigned.apk", directory / "aligned.apk", output / "tabs3-io-probe.apk"
        run(TOOLS / "aapt2", "link", "-I", JAR, "--manifest", manifest, "-o", unsigned)
        with zipfile.ZipFile(unsigned,"a",compression=zipfile.ZIP_DEFLATED) as archive: archive.write(dex / "classes.dex","classes.dex")
        run(TOOLS / "zipalign","-f","4",unsigned,aligned)
        run(*SIGNER,"sign","--ks",key,"--ks-key-alias","validation","--ks-pass","pass:tabs3-diagnostics","--key-pass","pass:tabs3-diagnostics","--out",apk,aligned)
        signature=subprocess.check_output([str(x) for x in [*SIGNER,"verify","--verbose","--print-certs",apk]],text=True)
        (output / "signature.txt").write_text(signature)
        permissions=subprocess.check_output([str(TOOLS / "aapt2"),"dump","permissions",str(apk)],text=True)
        if "android.permission.INTERNET" in permissions: raise ValueError("I/O probe must not have Internet permission")
        (output / "permissions.txt").write_text(permissions)
        (output / "build.json").write_text(json.dumps({"apk_sha256":digest(apk),"sdk":36,"sources":{str(p.relative_to(ROOT)):digest(p) for p in sources},
            "scope":"Ordinary camera/microphone permissions granted only to this temporary diagnostic; media content is never saved or exported"},indent=2)+"\n")
        (output / "SHA256SUMS").write_text(digest(apk)+"  "+apk.name+"\n")
    archive_payload(output)
    print("Built and verified I/O diagnostic: "+str(apk),flush=True)


if __name__ == "__main__": main()

#!/usr/bin/env python3
"""Download stable, compatible F-Droid APKs with signed-index/hash checks."""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO = "https://f-droid.org/repo"
# Published by https://f-droid.org/docs/Release_Channels_and_Signing_Keys/
REPO_SIGNER = "43238d512c1e5eb2d6569f4a3afbf5523418b82e0a3ed1552770abb9a9c9ccab"
DEFAULT_PACKAGES = ("org.fdroid.fdroid", "org.mozilla.fennec_fdroid",
                    "com.kgurgul.cpuinfo", "net.tlfoxhuman.droidstress",
                    "de.baumann.browser")


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") \
            else hashlib.sha256(stream.read()).hexdigest()


def run(command, destination, timeout=300):
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        def decoded(value):
            return value.decode(errors="replace") if isinstance(value, bytes) else value or ""
        destination.write_text(decoded(error.stdout) + "\nSTDERR:\n" + decoded(error.stderr)
                               + "\nTIMEOUT: " + str(timeout) + " seconds\n")
        raise
    destination.write_text(result.stdout + "\nSTDERR:\n" + result.stderr)
    if result.returncode:
        raise RuntimeError("Command failed; see " + str(destination))
    return result.stdout


def download(record, directory, mirror):
    name = record["name"]
    if not re.fullmatch(r"/[A-Za-z0-9_.-]+", name):
        raise ValueError("Unexpected repository filename")
    target = directory / name[1:]
    if not target.exists() or target.stat().st_size != record["size"] \
            or sha256(target) != record["sha256"]:
        partial = target.with_suffix(target.suffix + ".partial")
        run(["curl", "--fail", "--location", "--silent", "--show-error",
             "--proto", "=https", "--tlsv1.2", "--retry", "2", "--max-time", "300",
             "--output", str(partial), mirror + name],
            directory / (target.name + ".download.txt"), timeout=330)
        if partial.stat().st_size != record["size"] or sha256(partial) != record["sha256"]:
            raise ValueError("Downloaded size or hash differs from signed index: " + target.name)
        partial.replace(target)
    return target


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--entry", type=pathlib.Path, required=True)
    parser.add_argument("--index", type=pathlib.Path, required=True)
    parser.add_argument("--sdk", type=int, default=36)
    parser.add_argument("--abi", default="arm64-v8a")
    parser.add_argument("--package", action="append")
    parser.add_argument("--mirror", default=REPO, help="An HTTPS mirror present in the signed index")
    parser.add_argument("--reuse-from", type=pathlib.Path,
                        help="Reuse exact APK bytes from an older verified artifacts directory")
    args = parser.parse_args()
    directory = args.output.resolve()
    if not directory.is_relative_to(ROOT / "artifacts"):
        raise ValueError("Keep payloads under artifacts")
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    reuse = args.reuse_from.resolve() if args.reuse_from else None
    if reuse is not None and (not reuse.is_relative_to(ROOT / "artifacts")
                              or not reuse.is_dir() or reuse.is_symlink()):
        raise ValueError("Reuse only a real directory under artifacts")
    report = {"complete": False, "repository": REPO, "repo_signer_sha256": REPO_SIGNER,
              "signer_reference": "https://f-droid.org/docs/Release_Channels_and_Signing_Keys/",
              "selection": "Latest stable compatible APK, matching preferred signer",
              "sdk": args.sdk, "abi": args.abi, "packages": [],
              "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        entry_path = directory / "entry.jar"
        shutil.copyfile(args.entry, entry_path)
        verified = run(["jarsigner", "-verify", "-verbose", "-certs", str(entry_path)],
                       directory / "entry-jar-verification.txt")
        if "jar verified." not in verified or not re.search(r"^sm\s+\d+.*entry\.json\s*$", verified, re.M):
            raise ValueError("Signed entry.json verification was not established")
        cert = run(["keytool", "-printcert", "-jarfile", str(entry_path)],
                   directory / "entry-signer.txt")
        fingerprints = re.findall(r"SHA256:\s*([A-Fa-f0-9:]+)", cert)
        if len(fingerprints) != 1 or fingerprints[0].replace(":", "").lower() != REPO_SIGNER:
            raise ValueError("Repository signer does not match the published pin")
        with zipfile.ZipFile(entry_path) as archive:
            if len(archive.namelist()) != len(set(archive.namelist())):
                raise ValueError("Duplicate entry in signed repository JAR")
            entry_bytes = archive.read("entry.json")
        entry = json.loads(entry_bytes)
        (directory / "entry.json").write_bytes(entry_bytes)
        age = datetime.datetime.now(datetime.timezone.utc).timestamp() - entry["timestamp"] / 1000
        if not -86400 <= age <= 14 * 86400:
            raise ValueError("Signed index is outside the freshness window")
        index_record = entry["index"]
        if args.index.stat().st_size != index_record["size"] or sha256(args.index) != index_record["sha256"]:
            raise ValueError("Index differs from signed entry")
        report["index"] = index_record
        report["index_timestamp"] = entry["timestamp"]
        index = json.loads(args.index.read_text())
        mirrors = {m["url"].rstrip("/") for m in index["repo"].get("mirrors", [])}
        mirror = args.mirror.rstrip("/")
        if not mirror.startswith("https://") or mirror not in mirrors:
            raise ValueError("Use an HTTPS mirror listed in the verified index")
        report["download_mirror"] = mirror
        apksigner = ROOT / "android/prebuilts/sdk/tools/linux/lib/apksigner.jar"
        aapt = ROOT / "android/prebuilts/sdk/tools/linux/bin/aapt"
        for package in args.package or DEFAULT_PACKAGES:
            app = index["packages"][package]
            candidates = []
            for version in app["versions"].values():
                manifest = version["manifest"]
                sdk = manifest.get("usesSdk", {})
                native = manifest.get("nativecode", [])
                signers = manifest["signer"]["sha256"]
                if version.get("releaseChannels") or re.search(r"alpha|beta|rc", manifest["versionName"], re.I):
                    continue
                if sdk.get("minSdkVersion", 1) > args.sdk or sdk.get("maxSdkVersion", args.sdk) < args.sdk:
                    continue
                if native and args.abi not in native:
                    continue
                if app["metadata"].get("preferredSigner") not in signers:
                    continue
                candidates.append(version)
            if not candidates:
                raise ValueError("No stable compatible APK for " + package)
            version = max(candidates, key=lambda v: v["manifest"]["versionCode"])
            manifest = version["manifest"]
            print("Downloading " + package + " " + manifest["versionName"], flush=True)
            reused = False
            if reuse is not None:
                target_name = version["file"]["name"][1:]
                candidate = reuse / target_name
                target = directory / target_name
                if (candidate.is_file() and not candidate.is_symlink()
                        and candidate.stat().st_size == version["file"]["size"]
                        and sha256(candidate) == version["file"]["sha256"]):
                    os.link(candidate, target)
                    reused = True
            apk = download(version["file"], directory, mirror)
            signature = run(["java", "-Xmx256m", "-jar", str(apksigner), "verify", "--verbose", "--print-certs",
                             "--min-sdk-version", str(args.sdk), "--max-sdk-version", str(args.sdk), str(apk)],
                            directory / (package + ".signature.txt"))
            actual_signers = re.findall(r"Signer #\d+ certificate SHA-256 digest:\s*([a-f0-9]+)", signature)
            if not actual_signers or set(actual_signers) != set(manifest["signer"]["sha256"]):
                raise ValueError("APK signer differs from signed index")
            badging = run([str(aapt), "dump", "badging", str(apk)], directory / (package + ".badging.txt"))
            identity = re.search(r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", badging, re.M)
            if not identity or identity.groups() != (package, str(manifest["versionCode"]), manifest["versionName"]):
                raise ValueError("APK package/version differs from signed index")
            record = {"package": package, "version_name": manifest["versionName"],
                      "version_code": manifest["versionCode"], "file": apk.name,
                      "sha256": version["file"]["sha256"], "bytes": apk.stat().st_size,
                      "signers_sha256": actual_signers, "url": REPO + version["file"]["name"],
                      "download_url": mirror + version["file"]["name"],
                      "source_code": app["metadata"].get("sourceCode"),
                      "native_code": manifest.get("nativecode", []),
                      "signature_verified": True, "signed_index_hash_verified": True,
                      "reused_exact_apk": reused}
            report["packages"].append(record)
            print("Verified " + package, flush=True)
        report["complete"] = True
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        (directory / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Verified F-Droid payloads: " + str(directory), flush=True)


if __name__ == "__main__":
    main()

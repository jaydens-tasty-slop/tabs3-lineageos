#!/usr/bin/env python3
"""Install the verified F-Droid validation apps without replacing existing apps."""
import argparse
import datetime
import json
import os
import pathlib
import re
import shlex
import subprocess
import uuid

from adb_device import AdbDevice, private_directory
from device_smoke_common import file_hash, require

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGES = {"org.fdroid.fdroid", "org.mozilla.fennec_fdroid", "com.kgurgul.cpuinfo",
            "net.tlfoxhuman.droidstress", "de.baumann.browser"}


def installed_hash(device, package):
    locations = device.shell("pm path " + package, check=True).stdout.strip().splitlines()
    require(len(locations) == 1 and locations[0].startswith("package:/data/app/"), "Unexpected installed package location")
    path = locations[0][len("package:"):]
    require(re.fullmatch(r"/data/app/[A-Za-z0-9_./=+~-]+\.apk", path), "Unexpected APK path")
    return device.shell("sha256sum " + shlex.quote(path), check=True).stdout.split()[0]


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--payloads", type=pathlib.Path, required=True)
    parser.add_argument("--reuse-identical", action="store_true", help="Reuse existing APKs only after exact readback hash verification")
    args = parser.parse_args()
    device = AdbDevice(args.serial)
    require(not device.recovery and device.props.get("ro.build.version.sdk") == "37"
            and device.props.get("sys.boot_completed") == "1", "Booted Android 17 required")
    manifest = json.loads((args.payloads / "manifest.json").read_text())
    require(manifest["complete"] is True, "Incomplete download verification")
    selected = {r["package"] for r in manifest["packages"]}
    require(selected and selected <= PACKAGES and len(selected) == len(manifest["packages"]), "Unexpected or duplicate app set")
    existing = set()
    for item in manifest["packages"]:
        require(item["signature_verified"] and item["signed_index_hash_verified"], "Missing verification")
        require(re.fullmatch(r"[A-Za-z0-9_.-]+\.apk", item["file"]), "Unexpected APK filename")
        apk = args.payloads / item["file"]
        require(apk.is_file() and not apk.is_symlink() and file_hash(apk) == item["sha256"], "APK changed")
        if device.shell("pm path " + item["package"]).stdout.strip():
            require(args.reuse_identical and installed_hash(device, item["package"]) == item["sha256"],
                    "Existing app differs or reuse not requested; refusing replacement: " + item["package"])
            existing.add(item["package"])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = private_directory(ROOT / "diagnostics" / (stamp + "-fdroid-install-" + uuid.uuid4().hex[:8]))
    report = {"serial": args.serial, "passed": False, "packages": [],
              "manifest": str(args.payloads / "manifest.json"),
              "manifest_sha256": file_hash(args.payloads / "manifest.json"),
              "apps_retained_for_owner": True}
    report["framework_before"] = device.shell("pidof system_server; cat /proc/sys/kernel/random/boot_id", check=True).stdout
    try:
        for item in manifest["packages"]:
            if item["package"] not in existing:
                print("Installing " + item["package"] + " " + item["version_name"], flush=True)
                result = subprocess.run(device.command + ["install", "--no-streaming",
                                                           str(args.payloads / item["file"])],
                                        text=True, capture_output=True, timeout=180)
                (output / (item["package"] + ".install.txt")).write_text(result.stdout + "\nSTDERR:\n" + result.stderr)
                require(result.returncode == 0 and "Success" in result.stdout, "APK install failed")
            package = device.shell("dumpsys package " + item["package"], check=True).stdout
            (output / (item["package"] + ".package.txt")).write_text(package)
            require(re.search(r"\bversionCode=" + str(item["version_code"]) + r"\b", package), "Installed version mismatch")
            actual = installed_hash(device, item["package"])
            require(actual == item["sha256"], "Installed APK readback differs")
            report["packages"].append({**item, "installed_sha256": actual, "installed": True,
                                       "reused_identical": item["package"] in existing})
        report["framework_after"] = device.shell("pidof system_server; cat /proc/sys/kernel/random/boot_id", check=True).stdout
        report["framework_unchanged"] = report["framework_before"] == report["framework_after"]
        report["passed"] = report["framework_unchanged"]
    except Exception as error:
        report["error"] = str(error)
    finally:
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print("F-Droid install evidence: " + str(output / "report.json"), flush=True)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()

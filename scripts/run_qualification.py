#!/usr/bin/env python3
"""Run the public pytest device suite and emit concise JSON and JUnit results."""
import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent

def preflight(profile, requested_serial):
    sys.path.insert(0, str(ROOT / "scripts"))
    from adb_device import AdbDevice
    issues = []
    try:
        device = AdbDevice(requested_serial)
    except Exception as error:
        return requested_serial, ["ADB device selection failed: " + str(error)]
    if device.recovery:
        issues.append("Boot Android; recovery is not a qualification target.")
        return device.serial, issues
    if device.props.get("ro.build.version.sdk") != "37":
        issues.append("Boot Android 17 / SDK 37.")
    if device.props.get("sys.boot_completed") != "1":
        issues.append("Wait for Android to complete boot.")
    if device.shell("id -u").stdout.strip() != "2000":
        issues.append("ADB shell is not UID 2000; run `adb unroot`, reconnect, and retry.")
    if device.shell("am get-started-user-state 0").stdout.strip() != "RUNNING_UNLOCKED":
        issues.append("Unlock owner user 0 normally before running foreground tests.")
    policy = device.shell("dumpsys window policy").stdout
    if not ("mIsShowing=false" in policy or
            re.search(r"^\s*showing=false\s*$", policy, re.MULTILINE)):
        issues.append("Wake and unlock the current screen normally before running foreground tests.")
    local = {}
    if profile in ("quick", "full"):
        local["org.tabs3.validation.media"] = \
            ROOT / "artifacts/device-media-validation/tabs3-media-probe.apk"
    if profile == "full":
        local.update({
            "org.tabs3.validation.io": ROOT / "artifacts/device-io-validation/tabs3-io-probe.apk",
            "org.tabs3.validation.cameracontrols":
                ROOT / "artifacts/device-camera-controls/tabs3-camera-controls.apk",
        })
    for package, apk in local.items():
        found = device.shell("pm path " + package)
        paths = [line.removeprefix("package:") for line in found.stdout.splitlines()
                 if line.startswith("package:")]
        if not paths:
            continue
        if len(paths) != 1 or not paths[0].startswith("/data/app/"):
            issues.append("Unexpected installed path for diagnostic package " + package + ".")
            continue
        # The fixture deliberately uses `adb install -r` so an older build of
        # our throwaway probe cannot be mistaken for the current payload.  A
        # signature mismatch still fails safely at installation time.
    if profile == "full":
        for package in ("org.tabs3.validation.net", "org.tabs3.validation.noinet"):
            if device.shell("pm path " + package).stdout.strip():
                issues.append("A stale network probe is installed; remove it with "
                              "`adb uninstall " + package + "` and retry.")
    return device.serial, issues


def write_preflight_failure(output, stamp, profile, command, issues):
    suites = ET.Element("testsuites", tests="1", failures="1")
    suite = ET.SubElement(suites, "testsuite", name="qualification-preflight",
                          tests="1", failures="1")
    case = ET.SubElement(suite, "testcase", classname="qualification",
                         name="preflight", time="0")
    failure = ET.SubElement(case, "failure", message=issues[0])
    failure.text = "\n".join(issues)
    junit = output / "junit.xml"
    ET.ElementTree(suites).write(junit, encoding="unicode", xml_declaration=True)
    summary = {"created_utc": stamp, "profile": profile, "command": command,
               "exit_code": 2, "passed": False,
               "counts": {"passed": 0, "failed": 1, "skipped": 0},
               "tests": [{"name": "preflight", "class": "qualification",
                           "seconds": 0, "status": "failed",
                           "detail": " ".join(issues)}],
               "preflight_issues": issues, "junit": str(junit.relative_to(ROOT))}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("Preflight failed:")
    for issue in issues:
        print("- " + issue)
    print(json.dumps({"passed": False, "counts": summary["counts"],
                      "summary": str((output / "summary.json").relative_to(ROOT))}))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial")
    parser.add_argument("--profile", choices=("quick", "full", "browser"), default="quick")
    parser.add_argument("--provision-widevine", action="store_true",
                        help="Allow the media probe to provision Widevine over HTTPS")
    args = parser.parse_args()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = ROOT / "diagnostics" / (stamp + "-qualification-" + args.profile + "-" + uuid.uuid4().hex[:8])
    output.mkdir(parents=True, mode=0o700)
    expression = {"quick": "quick", "full": "quick or full", "browser": "browser"}[args.profile]
    junit = output / "junit.xml"
    command = [sys.executable, "-m", "pytest", "-c", str(ROOT / "qualification/pytest.ini"),
               str(ROOT / "qualification/test_device.py"), "-m", expression,
               "--result-root", str(output), "--junitxml", str(junit)]
    if args.serial:
        command += ["--serial", args.serial]
    if args.provision_widevine:
        command += ["--provision-widevine"]
    print("Qualification evidence: " + str(output), flush=True)
    selected_serial, issues = preflight(args.profile, args.serial)
    if issues:
        write_preflight_failure(output, stamp, args.profile, command, issues)
        raise SystemExit(2)
    if not args.serial:
        command += ["--serial", selected_serial]
    completed = subprocess.run(command, cwd=ROOT)
    cases = []
    if junit.is_file():
        root = ET.parse(junit).getroot()
        for case in root.iter("testcase"):
            status = "passed"
            detail = None
            for label in ("failure", "error", "skipped"):
                item = case.find(label)
                if item is not None:
                    status = "failed" if label in ("failure", "error") else "skipped"
                    lines = (item.text or "").strip().splitlines()
                    detail = item.get("message") or (lines[0] if lines else label)
                    break
            cases.append({"name": case.get("name"), "class": case.get("classname"),
                          "seconds": float(case.get("time", "0")), "status": status,
                          "detail": detail})
    summary = {"created_utc": stamp, "profile": args.profile, "command": command,
               "exit_code": completed.returncode,
               "passed": completed.returncode == 0 and bool(cases),
               "counts": {key: sum(row["status"] == key for row in cases)
                          for key in ("passed", "failed", "skipped")},
               "tests": cases, "junit": str(junit.relative_to(ROOT))}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"passed": summary["passed"], "counts": summary["counts"],
                      "summary": str((output / "summary.json").relative_to(ROOT))}))
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()

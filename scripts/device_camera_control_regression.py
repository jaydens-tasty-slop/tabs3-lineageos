#!/usr/bin/env python3
"""Normal foreground Camera2 lifecycle controls; no media saved."""
import argparse
import datetime
import json
import os
import pathlib
import re
import shlex
import subprocess
import time
import uuid
from adb_device import AdbDevice, private_directory
from device_smoke_common import file_hash, require

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = "org.tabs3.validation.cameracontrols"
ACTIVITY = PACKAGE + "/" + PACKAGE + ".MainActivity"


def keyguard_dismissed(policy):
    return ("mIsShowing=false" in policy or
            re.search(r"^\s*showing=false\s*$", policy, re.M) is not None)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--cycles", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--capture-choice", choices=("preview", "jpeg", "jpeg_idle"), required=True)
    parser.add_argument("--close-mode", choices=("direct", "drain"), required=True)
    parser.add_argument("--camera-id", choices=("0", "1", "both"), default="both")
    parser.add_argument("--preserve-active-stay-awake", action="store_true", help="Require outer USB stay-awake 2 and perform no settings writes")
    parser.add_argument("--expected-boot-id", help="Stop before changing app/device state if this boot is not active")
    parser.add_argument("--expected-build-date-utc", help="Require the already reviewed ROM build")
    parser.add_argument("--expected-core-pids", help="Require system_server,NetworkStack,SurfaceFlinger PIDs as a comma-separated triple")
    args = parser.parse_args()
    device = AdbDevice(args.serial)
    require(not device.recovery and device.props.get("sys.boot_completed") == "1"
            and device.props.get("ro.build.version.sdk") == "37", "Booted Android17 tablet required")
    require(device.shell("am get-started-user-state 0", check=True).stdout.strip() == "RUNNING_UNLOCKED",
            "The owner must unlock Android normally before the camera activity runs")
    require(keyguard_dismissed(device.shell("dumpsys window policy", check=True).stdout),
            "The current screen must be unlocked normally before this foreground camera test")
    identity = "pidof system_server; pidof com.android.networkstack.process; pidof surfaceflinger; cat /proc/sys/kernel/random/boot_id"
    initial_identity = device.shell(identity, check=True).stdout
    identity_lines = initial_identity.splitlines()
    require(len(identity_lines) == 4 and all(re.fullmatch(r"[0-9]+", line) for line in identity_lines[:3])
            and re.fullmatch(r"[0-9a-f-]{36}", identity_lines[3]), "Expected Android core and boot identities are unavailable")
    require(not args.expected_core_pids or ",".join(identity_lines[:3]) == args.expected_core_pids,
            "Android core identity differs from the coordinated checkpoint; stop foreground work")
    require(not args.expected_boot_id or identity_lines[3] == args.expected_boot_id,
            "Boot identity changed; do not continue foreground camera work on a different boot")
    require(not args.expected_build_date_utc or device.props.get("ro.build.date.utc") == args.expected_build_date_utc,
            "Build identity differs from the reviewed ROM")
    if args.preserve_active_stay_awake:
        require(device.shell("settings get global stay_on_while_plugged_in", check=True).stdout.strip() == "2",
                "Preserve the coordinated outer USB stay-awake session")
    payload = ROOT / "artifacts/device-camera-controls"
    apk = payload / "tabs3-camera-controls.apk"
    build = json.loads((payload / "build.json").read_text())
    require(file_hash(apk) == build["apk_sha256"], "I/O diagnostic APK changed")
    for source, expected_hash in build["sources"].items():
        require(file_hash(ROOT / source) == expected_hash, "I/O source differs from this archived APK: " + source)
    token = uuid.uuid4().hex[:8]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = private_directory(ROOT / "diagnostics" / (stamp + "-camera-api-controls-" + token))
    filename = "camera-control-" + token + ".json"
    report = {"serial": args.serial, "cycles_requested": args.cycles,
              "capture_choice": args.capture_choice, "close_mode": args.close_mode, "camera_id": args.camera_id, "apk_sha256": build["apk_sha256"],
              "passed": False, "provider_samples": [], "errors": [],
              "build_date_utc": device.props.get("ro.build.date.utc"),
              "framework_before": initial_identity,
              "framework_identity_order": ["system_server", "NetworkStack", "SurfaceFlinger", "boot_id"],
              "scope": "Ordinary foreground Camera2 activity, callbacks, provider PID and logcat; no photographs saved/exported, native library experiments, System writes or reboot"}
    (output / "build.json").write_text(json.dumps(build, indent=2) + "\n")
    (output / "harness.py").write_bytes(pathlib.Path(__file__).read_bytes())
    (output / "MainActivity.java").write_bytes((ROOT / "device-validation/camera-controls/src/org/tabs3/validation/cameracontrols/MainActivity.java").read_bytes())
    (output / "tabs3-camera-controls.apk").write_bytes(apk.read_bytes())
    installed_here = False
    permission_granted_here = False
    stay_awake = None
    app_owned = False
    provider = "pidof android.hardware.camera.provider@2.4-service"

    def adb(arguments, timeout=60, check=False):
        return subprocess.run(device.command + arguments, timeout=timeout, check=check,
                              capture_output=True, text=True)

    def sample_provider():
        require(device.shell(identity, check=True).stdout == initial_identity,
                "Android core or boot identity changed; camera workload stopped")
        require(device.shell("am get-started-user-state 0", check=True).stdout.strip() == "RUNNING_UNLOCKED" and
                keyguard_dismissed(device.shell("dumpsys window policy", check=True).stdout),
                "Normal unlock changed; stop foreground camera work")
        observed = device.shell(provider).stdout.strip()
        require(not observed or all(pid.isdecimal() for pid in observed.split()), "Unexpected camera provider PID")
        report["provider_samples"].append({"elapsed_seconds": round(time.monotonic() - start, 3), "pid": observed})
        return observed

    start = time.monotonic()
    try:
        lookup = device.shell("pm path " + PACKAGE)
        paths = [line.removeprefix("package:") for line in lookup.stdout.splitlines() if line.startswith("package:")]
        if paths:
            require(len(paths) == 1 and paths[0].startswith("/data/app/") and
                    device.shell("sha256sum " + shlex.quote(paths[0]), check=True).stdout.split()[0] == build["apk_sha256"],
                    "Existing diagnostic has different bytes; archive and explicitly remove only that diagnostic before replacing it")
        else:
            require(lookup.returncode in (0, 1), "Diagnostic package lookup failed")
            installed = adb(["install", "--no-streaming", str(apk)], timeout=120)
            (output / "install.txt").write_text(installed.stdout + installed.stderr)
            require(installed.returncode == 0 and "Success" in installed.stdout, "Diagnostic APK install failed")
            installed_here = True
        app_owned = True
        permission = device.shell("dumpsys package " + PACKAGE, check=True).stdout
        matches = re.findall(r"^\s*android\.permission\.CAMERA:\s+granted=(true|false)\b", permission, re.M)
        require(len(matches) <= 1 and (matches or installed_here),
                "Cannot determine this diagnostic's previous camera permission state")
        was_granted = bool(matches and matches[0] == "true")
        device.shell("pm grant " + PACKAGE + " android.permission.CAMERA", check=True)
        permission_granted_here = not was_granted
        previous_stay_awake = device.shell("settings get global stay_on_while_plugged_in", check=True).stdout.strip()
        require(previous_stay_awake == "null" or re.fullmatch(r"[0-7]", previous_stay_awake), "Unexpected stay-awake setting")
        stay_awake = previous_stay_awake
        if args.preserve_active_stay_awake:
            require(stay_awake == "2", "Outer stay-awake changed before workload")
        else:
            device.shell("settings put global stay_on_while_plugged_in 2", check=True)
        report["settings_write_performed"] = not args.preserve_active_stay_awake
        report["stay_awake_before"] = stay_awake
        report["provider_before"] = sample_provider()
        require(len(report["provider_before"].split()) == 1, "Exactly one camera provider required")
        (output / "camera-service-before.txt").write_text(device.shell("dumpsys media.camera").stdout)
        (output / "sensor-privacy-before.txt").write_text(device.shell("dumpsys sensor_privacy").stdout)
        device.shell("am force-stop " + PACKAGE, check=True)
        launch = device.shell("am start -W -n " + ACTIVITY + " --es capture_choice " + args.capture_choice + " --es close_mode " + args.close_mode +
                              " --es camera_id " + args.camera_id + " --ei cycles " + str(args.cycles) + " --es output " + filename, timeout=30)
        (output / "launch.txt").write_text(launch.stdout + launch.stderr)
        require(launch.returncode == 0 and "Error:" not in launch.stdout, "Camera diagnostic activity failed to launch")
        deadline = time.monotonic() + 240
        item = None
        while time.monotonic() < deadline:
            sample_provider()
            raw = adb(["exec-out", "run-as", PACKAGE, "cat", "files/" + filename], timeout=10)
            if raw.returncode == 0 and raw.stdout.lstrip().startswith("{"):
                item = json.loads(raw.stdout)
                break
            time.sleep(.5)
        require(item is not None, "Camera activity report timed out")
        report["app_result"] = item
        (output / "app-result.json").write_text(json.dumps(item, indent=2) + "\n")
        require(isinstance(item.get("client_uid"), int) and item["client_uid"] >= 10000,
                "Camera result must come from the ordinary installed app")
        for _ in range(10):
            time.sleep(.5)
            sample_provider()
    except Exception as error:
        report["errors"].append(str(error))
    finally:
        if app_owned:
            device.shell("am force-stop " + PACKAGE)
            device.shell("run-as " + PACKAGE + " rm -f files/" + filename)
            if installed_here:
                removed = adb(["uninstall", PACKAGE])
                report["probe_removed"] = removed.returncode == 0 and "Success" in removed.stdout
            elif permission_granted_here:
                revoked = device.shell("pm revoke " + PACKAGE + " android.permission.CAMERA")
                report["temporary_camera_permission_revoked"] = revoked.returncode == 0
        if stay_awake is not None:
            command = ("settings delete global stay_on_while_plugged_in" if stay_awake == "null" else
                       "settings put global stay_on_while_plugged_in " + stay_awake)
            restored = None if args.preserve_active_stay_awake else device.shell(command)
            actual = device.shell("settings get global stay_on_while_plugged_in").stdout.strip()
            report["stay_awake_restored"] = (restored is None or restored.returncode == 0) and actual == stay_awake
            report["stay_awake_preserved"] = args.preserve_active_stay_awake and actual == "2"
        report["provider_after"] = device.shell(provider).stdout.strip()
        report["framework_after"] = device.shell(identity).stdout
        report["framework_unchanged"] = report.get("framework_before") == report["framework_after"]
        report["normal_unlock_preserved"] = (device.shell("am get-started-user-state 0").stdout.strip() == "RUNNING_UNLOCKED" and
            keyguard_dismissed(device.shell("dumpsys window policy").stdout))
        report["provider_unchanged"] = (bool(report.get("provider_before")) and
            all(item["pid"] == report["provider_before"] for item in report["provider_samples"]) and
            report["provider_after"] == report["provider_before"])
        for name, command in (("camera-service-after", "dumpsys media.camera"),
                              ("crash-buffer", "logcat -b crash -d -v threadtime"),
                              ("logcat", "logcat -b all -d -v threadtime -t 30000")):
            captured = device.shell(command, timeout=45)
            (output / (name + ".txt")).write_text(captured.stdout + captured.stderr)
        report["elapsed_seconds"] = round(time.monotonic() - start, 3)
        report["passed"] = (not report["errors"] and report.get("app_result", {}).get("passed") is True and
            report["provider_unchanged"] and report["framework_unchanged"] and report["normal_unlock_preserved"] and
            report.get("stay_awake_restored") is True and
            (not installed_here or report.get("probe_removed") is True) and
            (not permission_granted_here or installed_here or report.get("temporary_camera_permission_revoked") is True))
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print("Ordinary Camera2 control report: " + str(output / "report.json") + "; passed=" + str(report["passed"]), flush=True)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Observe the pinned tablet's framework and logcat without changing device state."""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import time
import uuid

from adb_device import AdbDevice, private_directory

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--seconds", type=int, default=300)
    args = parser.parse_args()
    if not 10 <= args.seconds <= 1800:
        parser.error("Use an observation duration from 10 to 1800 seconds")
    device = AdbDevice(args.serial)
    if device.recovery or device.props.get("ro.build.version.sdk") != "37":
        raise SystemExit("This observer requires the Android 17 tablet")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = private_directory(ROOT / "diagnostics" /
                                  (stamp + "-framework-stability-" + uuid.uuid4().hex[:8]))
    report = {"serial": device.serial, "started_utc": stamp, "samples": [],
              "limits": ["An unchanged PID does not establish hardware functionality",
                         "boot_completed can remain set after a framework crash"]}
    report_path = directory / "report.json"
    print("Evidence: " + str(directory), flush=True)
    for name, command in {
        "recent-logcat": "logcat -b all -d -v threadtime -t 30000",
        "camera": "dumpsys media.camera",
        "audio": "dumpsys media.audio_flinger; dumpsys media.audio_policy; dumpsys audio",
        "recorder-exit": "dumpsys activity exit-info org.lineageos.recorder",
        "storage": "sm list-volumes all; df /storage/emulated/0 /storage/9A88-A115",
    }.items():
        try:
            result = device.shell(command, timeout=20)
            (directory / (name + ".txt")).write_text(result.stdout + "\nSTDERR:\n" + result.stderr)
        except (OSError, subprocess.TimeoutExpired) as error:
            (directory / (name + ".txt")).write_text(str(error))
    started = time.monotonic()
    with (directory / "live-logcat.txt").open("w") as output:
        process = subprocess.Popen(device.command + ["logcat", "-b", "all", "-v", "threadtime"],
                                   stdout=output, stderr=subprocess.STDOUT)
        try:
            while time.monotonic() - started < args.seconds:
                sample = {"elapsed_seconds": round(time.monotonic() - started, 2),
                          "observed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
                try:
                    result = device.shell(
                        "getprop sys.boot_completed; pidof system_server; cat /proc/uptime; "
                        "cat /proc/sys/kernel/random/boot_id", timeout=10)
                    sample.update({"exit_status": result.returncode, "stdout": result.stdout,
                                   "stderr": result.stderr})
                    lines = result.stdout.splitlines()
                    if result.returncode == 0 and len(lines) == 4:
                        sample.update({"boot_completed": lines[0], "system_server_pid": lines[1],
                                       "uptime_seconds": float(lines[2].split()[0]), "boot_id": lines[3]})
                except (OSError, subprocess.TimeoutExpired, ValueError) as error:
                    sample["error"] = str(error)
                report["samples"].append(sample)
                report_path.write_text(json.dumps(report, indent=2) + "\n")
                time.sleep(min(10, max(0, args.seconds - (time.monotonic() - started))))
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    valid = [sample for sample in report["samples"] if "boot_id" in sample]
    report["complete"] = True
    report["same_framework_and_boot_observed"] = (
        len(valid) == len(report["samples"]) and len(valid) >= 2
        and all(sample["boot_completed"] == "1" and sample["system_server_pid"] for sample in valid)
        and len({sample["system_server_pid"] for sample in valid}) == 1
        and len({sample["boot_id"] for sample in valid}) == 1)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print("Same framework/boot observed: " + str(report["same_framework_and_boot_observed"]), flush=True)
    raise SystemExit(0 if report["same_framework_and_boot_observed"] else 1)


if __name__ == "__main__":
    main()

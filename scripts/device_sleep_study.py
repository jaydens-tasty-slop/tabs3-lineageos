#!/usr/bin/env python3
"""Bracket unplugged standby with one-shot snapshots; no on-device logger."""
import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import time
import uuid

from adb_device import AdbDevice, AdbDeviceNotReady, private_directory
from device_smoke_common import file_hash, require

ROOT = pathlib.Path(__file__).resolve().parent.parent
ACTIVE = ROOT / "state/active-sleep-study.json"
CLOCK_COMMAND = ("date +%s; cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; "
                 "awk '/now at/{print;exit}' /proc/timer_list")
PROBES = {
    "battery": "dumpsys battery",
    "batterystats": "dumpsys batterystats --charged",
    "battery-history": "dumpsys batterystats --history",
    "battery-current-csv": "dumpsys batterystats -c",
    "power": "dumpsys power",
    "deviceidle": "dumpsys deviceidle",
    "alarm": "dumpsys alarm",
    "jobs": "dumpsys jobscheduler",
    "wifi": "cmd wifi status",
    "kernel-log": "dmesg",
    "last-kernel-log": "cat /proc/last_kmsg",
    "interrupts": "cat /proc/interrupts",
    "wakeup-sources": "cat /sys/kernel/debug/wakeup_sources",
    "suspend-stats": "cat /sys/kernel/debug/suspend_stats",
    "rpm-stats": "cat /sys/kernel/debug/rpm_stats",
    "rpm-master-stats": "cat /sys/kernel/debug/rpm_master_stats",
    "suspend-time": "cat /sys/kernel/debug/sleep_time",
    "power-supplies": ("for d in /sys/class/power_supply/battery /sys/class/power_supply/bms; do "
                       "for n in capacity charge_counter charge_full charge_full_design current_now "
                       "current_avg voltage_now temp status; do "
                       "if [ -r \"$d/$n\" ]; then printf '%s=' \"$d/$n\"; cat \"$d/$n\"; fi; done; done"),
}
# /sys/power/wakeup_count waits for active wake events to finish on this kernel.
# Read the nonblocking cumulative debugfs wakeup_sources table instead.


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def ready(serial):
    deadline = time.monotonic() + 45
    while True:
        try:
            return AdbDevice(serial)
        except (AdbDeviceNotReady, subprocess.SubprocessError, OSError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.5)


def identity(device):
    rows = device.shell("cat /proc/sys/kernel/random/boot_id; pidof system_server; "
                        "pidof com.android.networkstack.process; pidof surfaceflinger",
                        check=True).stdout.strip().splitlines()
    require(len(rows) == 4 and re.fullmatch(r"[0-9a-f-]{36}", rows[0])
            and all(row.isdecimal() for row in rows[1:]), "Incomplete Android identity")
    return rows


def parse_clock(text):
    rows = text.splitlines()
    match = re.search(r"^now at (\d+) nsecs$", text, re.M)
    return {"unix_seconds": int(rows[0]), "boot_id": rows[1],
            "boottime_seconds": float(rows[2].split()[0]),
            "monotonic_ns": int(match[1]) if match else None}


def parse_battery(text):
    result = {}
    for field in ("level", "scale", "voltage", "temperature", "Charge counter", "status"):
        match = re.search(r"^\s*" + re.escape(field) + r": (-?\d+)\s*$", text, re.M)
        result[field] = int(match[1]) if match else None
    return result


def wakeup_rows(path):
    if not path.is_file():
        return {}
    text = path.read_text().split("\nSTDERR:", 1)[0]
    lines = [line.split() for line in text.splitlines() if line.strip()]
    if not lines or "wakeup_count" not in lines[0]:
        return {}
    columns = lines[0]
    rows = {}
    for fields in lines[1:]:
        if len(fields) == len(columns) and all(value.isdecimal() for value in fields[1:]):
            rows[fields[0]] = dict(zip(columns[1:], map(int, fields[1:])))
    return rows


def wakeup_deltas(start_directory, finish_directory):
    before = wakeup_rows(start_directory / "wakeup-sources.txt")
    after = wakeup_rows(finish_directory / "wakeup-sources.txt")
    result = []
    for name in before.keys() & after.keys():
        values = {key: after[name][key] - before[name][key] for key in
                  ("active_count", "event_count", "wakeup_count", "expire_count", "total_time",
                   "prevent_suspend_time") if key in before[name] and key in after[name]}
        if any(values.values()):
            result.append({"name": name, "delta": values,
                           "counter_reset_seen": any(value < 0 for value in values.values())})
    result.sort(key=lambda row: (row["delta"].get("prevent_suspend_time", 0),
                                row["delta"].get("wakeup_count", 0)), reverse=True)
    return {"available": bool(before and after), "duration_unit": "milliseconds",
            "common_sources": len(before.keys() & after.keys()), "changed_sources": result,
            "limits": "Driver changes can add/remove wake sources; endpoint USB activity is included"}


def capture(serial, output, final_anchor):
    device = ready(serial)
    require(not device.recovery and device.props.get("ro.build.version.sdk") == "36"
            and device.props.get("sys.boot_completed") == "1", "Booted Android 16 required")
    original_uid = device.shell("id -u", check=True).stdout.strip()
    require(original_uid in ("0", "2000"), "Unexpected ADB identity")
    stay = device.shell("settings get global stay_on_while_plugged_in", check=True).stdout.strip()
    require(stay == "null" or re.fullmatch(r"\d+", stay), "Unexpected USB stay-awake setting")
    report = {"complete": False, "serial": serial, "original_adb_uid": original_uid,
              "stay_awake": stay, "initial_identity": identity(device), "probes": {},
              "build_date_utc": device.props.get("ro.build.date.utc"), "root_requested": False,
              "scope": "Read-only endpoint observations; temporary root ADB for kernel counters only"}
    report_path = output / "snapshot.json"
    battery = device.shell("dumpsys battery", check=True).stdout
    (output / "battery-at-connection.txt").write_text(battery)
    require("USB powered: true" in battery and "UPDATES STOPPED" not in battery.upper(),
            "Connect USB with the real battery service enabled")
    report["battery_at_connection"] = parse_battery(battery)
    try:
        if original_uid == "2000":
            report["root_requested"] = True
            request = subprocess.run(device.command + ["root"], capture_output=True, text=True, timeout=10)
            (output / "adb-root-request.txt").write_text(request.stdout + request.stderr)
            device = ready(serial)
        report["collection_adb_uid"] = device.shell("id -u", check=True).stdout.strip()
        if not final_anchor:
            clock = device.shell(CLOCK_COMMAND, timeout=15)
            (output / "clock-anchor.txt").write_text(clock.stdout + clock.stderr)
            report["clock"] = parse_clock(clock.stdout)
        for name, command in PROBES.items():
            try:
                result = device.shell(command, timeout=45)
                path = output / (name + ".txt")
                path.write_text(result.stdout + "\nSTDERR:\n" + result.stderr)
                report["probes"][name] = {"returncode": result.returncode,
                    "available": result.returncode == 0 and bool(result.stdout.strip()),
                    "sha256": file_hash(path), "command": command}
            except (subprocess.SubprocessError, OSError) as error:
                report["probes"][name] = {"available": False, "error": str(error)}
        if final_anchor:
            # Take the start clock/battery after other probes, and the finish
            # clock before probes, to reduce USB observation in the interval.
            clock = device.shell(CLOCK_COMMAND, timeout=15)
            (output / "clock-anchor.txt").write_text(clock.stdout + clock.stderr)
            report["clock"] = parse_clock(clock.stdout)
            report["battery_at_anchor"] = parse_battery(device.shell("dumpsys battery", check=True).stdout)
        report["final_identity"] = identity(device)
        require(report["final_identity"] == report["initial_identity"], "Core processes changed during capture")
        report["complete"] = True
    finally:
        try:
            device = ready(serial)
            if original_uid == "2000" and device.shell("id -u", check=True).stdout.strip() == "0":
                subprocess.run(device.command + ["unroot"], check=True, capture_output=True, timeout=10)
                device = ready(serial)
            report["adb_uid_restored"] = device.shell("id -u", check=True).stdout.strip() == original_uid
            report["stay_awake_unchanged"] = device.shell(
                "settings get global stay_on_while_plugged_in", check=True).stdout.strip() == stay
        except (ValueError, subprocess.SubprocessError, OSError) as error:
            report["restore_error"] = str(error)
            report["adb_uid_restored"] = False
        if not report.get("adb_uid_restored") or not report.get("stay_awake_unchanged"):
            report["complete"] = False
        save_json(report_path, report)
    require(report["complete"], "Endpoint capture/ADB restoration failed; inspect snapshot.json")
    return report


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    start = sub.add_parser("start")
    start.add_argument("--serial", required=True)
    start.add_argument("--hours", type=float, default=12)
    finish = sub.add_parser("finish")
    finish.add_argument("--study", type=pathlib.Path,
                        help="Study manifest; defaults to state/active-sleep-study.json")
    args = parser.parse_args()
    if args.action == "start":
        require(1 <= args.hours <= 48, "Use a 1–48-hour study")
        if ACTIVE.exists():
            previous = json.loads(ACTIVE.read_text())
            require(json.loads((ROOT / previous["manifest"]).read_text()).get("complete") is True,
                    "Finish the active study before starting another")
        device = ready(args.serial)
        require(device.shell("settings get global stay_on_while_plugged_in", check=True).stdout.strip()
                in ("0", "null"), "Finish foreground tests and restore USB stay-awake before arming")
        require(device.shell("settings get global adb_wifi_enabled", check=True).stdout.strip() in ("0", "null")
                and all(device.props.get(name, "") in ("", "-1", "0") for name in
                        ("service.adb.tcp.port", "persist.adb.tcp.port")),
                "Disable wireless/network ADB before the standby study")
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = private_directory(ROOT / "diagnostics" / (stamp + "-sleep-study-" + uuid.uuid4().hex[:8]))
        (output / "device_sleep_study.py").write_bytes(pathlib.Path(__file__).read_bytes())
        begin = private_directory(output / "start")
        baseline = capture(args.serial, begin, final_anchor=True)
        manifest = output / "manifest.json"
        save_json(manifest, {"complete": False, "serial": args.serial, "requested_hours": args.hours,
            "start_snapshot": str((begin / "snapshot.json").relative_to(ROOT)),
            "build_date_utc": baseline["build_date_utc"], "created_utc": stamp,
            "on_device_logger": False, "wireless_adb_enabled": False,
            "instructions": "Unplug USB, turn the screen off, leave on usual Wi-Fi for the study; reconnect USB and finish before using/charging/rebooting"})
        save_json(ACTIVE, {"manifest": str(manifest.relative_to(ROOT))})
        print("Study ready: " + str(manifest.relative_to(ROOT)))
        print("Unplug USB, turn the screen off and leave unused for " + str(args.hours) + " hours on usual Wi-Fi.")
        print("After reconnecting USB: sh scripts/device.sh exec python3 scripts/device_sleep_study.py finish")
        return
    require(args.study is not None or ACTIVE.is_file(), "No active study; run start first")
    manifest_path = (args.study.resolve() if args.study else
                     (ROOT / json.loads(ACTIVE.read_text())["manifest"]).resolve())
    require(manifest_path.is_relative_to(ROOT / "diagnostics") and manifest_path.name == "manifest.json",
            "Use a workspace sleep-study manifest")
    manifest = json.loads(manifest_path.read_text())
    require(manifest.get("complete") is False, "Study already finished")
    baseline = json.loads((ROOT / manifest["start_snapshot"]).read_text())
    end_dir = private_directory(manifest_path.parent / ("finish-" + uuid.uuid4().hex[:8]))
    end = capture(manifest["serial"], end_dir, final_anchor=False)
    a, b = baseline["clock"], end["clock"]
    same_boot = a["boot_id"] == b["boot_id"]
    elapsed = b["boottime_seconds"] - a["boottime_seconds"] if same_boot else None
    awake = ((b["monotonic_ns"] - a["monotonic_ns"]) / 1e9
             if same_boot and a["monotonic_ns"] is not None and b["monotonic_ns"] is not None else None)
    start_battery = baseline["battery_at_anchor"]
    end_battery = end["battery_at_connection"]
    levels_available = all(value["level"] is not None and value["scale"] == 100
                           for value in (start_battery, end_battery))
    drain = start_battery["level"] - end_battery["level"] if levels_available else None
    analysis = {"same_boot": same_boot, "same_build": baseline["build_date_utc"] == end["build_date_utc"],
        "requested_hours": manifest["requested_hours"],
        "elapsed_hours_including_USB_brackets": elapsed / 3600 if elapsed and elapsed > 0 else None,
        "kernel_awake_seconds": awake,
        "kernel_suspended_seconds": max(0, elapsed - awake) if elapsed and awake is not None else None,
        "kernel_suspend_fraction": max(0, min(1, (elapsed - awake) / elapsed)) if elapsed and elapsed > 0 and awake is not None else None,
        "battery_start_percent": start_battery["level"], "battery_end_percent": end_battery["level"],
        "battery_drain_percentage_points": drain,
        "battery_drain_points_per_hour": drain / (elapsed / 3600) if drain is not None and elapsed and elapsed > 0 else None,
        "core_processes_unchanged": baseline["initial_identity"] == end["initial_identity"],
        "requires_history_review": True,
        "limits": ["Battery history determines the actual unplugged interval, screen-on use and intervening charge events",
                   "Endpoint clocks include brief USB/root-ADB observation and unplug/reconnect delays",
                   "Kernel suspend time does not prove the deepest Qualcomm power state; inspect RPM counters",
                   "Percentage readings are coarse; vendor charge/current readings need separate qualification",
                   "No pass/fail battery-drain threshold or general battery-health claim is inferred"]}
    if same_boot:
        analysis["kernel_wakeup_source_deltas"] = wakeup_deltas(
            (ROOT / manifest["start_snapshot"]).parent, end_dir)
    save_json(manifest_path.parent / "analysis.json", analysis)
    manifest.update(complete=True, finish_snapshot=str((end_dir / "snapshot.json").relative_to(ROOT)),
                    analysis=str((manifest_path.parent / "analysis.json").relative_to(ROOT)))
    save_json(manifest_path, manifest)
    summary = {key: analysis[key] for key in
               ("same_boot", "same_build", "elapsed_hours_including_USB_brackets",
                "battery_start_percent", "battery_end_percent", "battery_drain_points_per_hour",
                "kernel_suspend_fraction", "core_processes_unchanged")}
    print(json.dumps(summary, indent=2))
    print("Battery history still needs review for actual unplug time, screen use and charging.")
    print("Sleep-study evidence: " + str(manifest_path.parent.relative_to(ROOT)))


if __name__ == "__main__":
    main()

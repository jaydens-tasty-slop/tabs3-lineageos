#!/usr/bin/env python3
"""Run a read-only basic health check on one booted Tab S3 over ADB."""
import argparse
import re
import subprocess
import sys


def fail(message):
    print("FAIL: " + message, file=sys.stderr)
    raise SystemExit(1)


def command(*args, timeout=30, operation=None):
    result = subprocess.run(["adb", *args], text=True, capture_output=True,
                            timeout=timeout)
    if result.returncode:
        fail("ADB %s failed (exit %d)" % (operation or "command", result.returncode))
    return result.stdout.strip()


def shell(serial, command_text, timeout=30):
    return command("-s", serial, "shell", command_text, timeout=timeout,
                   operation="shell " + command_text)


def require(condition, message):
    if not condition:
        fail(message)


def select_device(requested):
    listing = command("devices")
    rows = []
    for line in listing.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 2:
            rows.append((fields[0], fields[1]))

    if requested:
        require(re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", requested) is not None,
                "SERIAL contains unsupported characters")
        matches = [state for serial, state in rows if serial == requested]
        require(len(matches) == 1 and matches[0] == "device",
                "Selected ADB device is not connected and authorized")
        return requested

    require(len(rows) == 1,
            "Connect one authorized device or pass SERIAL=... to select one")
    require(rows[0][1] == "device", "The connected ADB device is not authorized and ready")
    return rows[0][0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", help="Select one device from adb devices")
    args = parser.parse_args()

    serial = select_device(args.serial)
    identity = [
        shell(serial, "getprop ro.product.model"),
        shell(serial, "getprop ro.product.vendor.model"),
        shell(serial, "getprop ro.product.device"),
        shell(serial, "getprop ro.build.product"),
        shell(serial, "getprop ro.product.vendor.device"),
    ]
    normalized = {value.strip().upper() for value in identity if value.strip()}
    require("SM-T825" not in normalized and "GTS3LLTE" not in normalized,
            "The LTE SM-T825 is outside this build's supported target")
    require("SM-T820" in normalized or "GTS3LWIFI" in normalized,
            "Device identity is not SM-T820/gts3lwifi")

    require(shell(serial, "getprop ro.build.version.sdk") == "36",
            "Android API level is not 36")
    require(shell(serial, "getprop sys.boot_completed") == "1",
            "Android has not completed boot")
    require(not shell(serial, "getprop ro.twrp.version"),
            "The device is in recovery, not Android")
    require(bool(shell(serial, "pidof system_server")),
            "system_server is not running")
    print("Device identity and Android 16 boot: OK")

    for service in ("activity", "package"):
        status = shell(serial, "service check " + service)
        require(re.fullmatch(r"Service\s+" + re.escape(service) + r":\s+found",
                             status, re.IGNORECASE) is not None,
                service + " service is unavailable")
    print("Activity and package services: OK")

    mounts = shell(serial, "cat /proc/mounts")
    mounted_apexes = {"runtime": set(), "art": set()}
    for line in mounts.splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        match = re.fullmatch(
            r"/apex/com\.android\.(runtime|art)(?:@[^/]*)?", fields[1])
        if match:
            mounted_apexes[match.group(1)].add(fields[1])
    for name, mountpoints in mounted_apexes.items():
        require(mountpoints, "Required live APEX mount is unavailable: " + name)

    for path in ("/apex/com.android.runtime/bin/linker64",
                 "/apex/com.android.art/bin/odrefresh"):
        executable = shell(serial, "if test -x " + path + "; then echo yes; else echo missing; fi")
        require(executable == "yes",
                "Required APEX executable is unavailable: " + path)
    packages = shell(serial, "pm list packages -s")
    require(any(line.startswith("package:") for line in packages.splitlines()),
            "System package inventory is empty")
    print("Runtime/ART APEX mounts, executables and system package inventory: OK")

    crash_buffer = shell(serial, "logcat -b crash -d -t 200")
    crash_lines = [line for line in crash_buffer.splitlines()
                   if line.strip() and not line.startswith("--------- beginning of ")]
    require(not crash_lines,
            "Crash buffer has %d non-header output lines; log text was not printed or saved"
            % len(crash_lines))
    print("Last 200 crash-buffer log entries: clear")
    print("Read-only smoke passed; no device files or partitions were changed")


if __name__ == "__main__":
    try:
        main()
    except subprocess.TimeoutExpired:
        fail("ADB command timed out")
    except FileNotFoundError:
        fail("ADB is unavailable in the device tools container")

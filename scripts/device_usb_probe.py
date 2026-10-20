#!/usr/bin/env python3
"""Check ordinary app socket permissions and UID accounting over USB or Wi-Fi."""
import argparse
import datetime
import json
import ipaddress
import os
import pathlib
import re
import shlex
import socket
import subprocess
import time
import uuid

from adb_device import AdbDevice, private_directory
from device_smoke_common import file_hash, require

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGES = {"org.tabs3.validation.net": "tabs3-probe-net.apk",
            "org.tabs3.validation.noinet": "tabs3-probe-noinet.apk"}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial")
    parser.add_argument("--expected-sdk", type=int)
    parser.add_argument("--port", type=int, default=18023)
    parser.add_argument("--transport", choices=("usb", "wifi"), default="usb")
    args = parser.parse_args()
    require(1024 <= args.port <= 65535, "Use an unprivileged port")
    device = AdbDevice(args.serial)
    require(not device.recovery and device.props.get("sys.boot_completed") == "1",
            "Requires a booted Android system")
    if args.expected_sdk is not None:
        require(device.props.get("ro.build.version.sdk") == str(args.expected_sdk), "Unexpected SDK")
    require(device.shell("am get-started-user-state 0",check=True).stdout.strip()=="RUNNING_UNLOCKED",
            "Normal first unlock is required for ordinary app network tests")
    build_directory = ROOT / "artifacts/device-validation"
    build = json.loads((build_directory / "build.json").read_text())
    built_apks = {item["package"]: item for item in build["apks"]}
    require(len(build["apks"]) == len(PACKAGES) and set(built_apks) == set(PACKAGES),
            "Unexpected network probe packages in build manifest")
    apk_hashes = {}
    for package, filename in PACKAGES.items():
        item = built_apks[package]
        apk = build_directory / filename
        require(item["file"] == filename and apk.is_file() and not apk.is_symlink(),
                "Missing or unexpected network probe APK")
        apk_hashes[package] = file_hash(apk)
        require(apk_hashes[package] == item["sha256"], "Network probe APK checksum changed")
    bind="127.0.0.1";tablet_address=None;wifi_route=None
    if args.transport=="wifi":
        addresses=device.shell("ip -4 addr show dev wlan0",check=True).stdout
        matches=re.findall(r"\binet (\d+\.\d+\.\d+\.\d+/\d+)\b",addresses)
        require(len(matches)==1,"A connected wlan0 with one IPv4 address is required")
        interface=ipaddress.ip_interface(matches[0]);tablet_address=str(interface.ip)
        require(interface.ip.is_private and not interface.ip.is_loopback,"Use the connected private Wi-Fi network")
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as route:
            route.connect((tablet_address,9));bind=route.getsockname()[0]
        require(ipaddress.ip_address(bind) in interface.network and bind!=tablet_address,
                "Host must share the tablet's Wi-Fi LAN")
        wifi_route=device.shell("ip -4 route get "+bind,check=True).stdout
        require(re.search(r"\bdev wlan0\b",wifi_route),"Probe destination is not routed over Wi-Fi")
    for package in PACKAGES:
        require(not device.shell("pm path " + package).stdout.strip(),
                "Probe app is already installed; refusing to replace it: " + package)
    port = "tcp:" + str(args.port)
    if args.transport=="usb":
        listing = subprocess.check_output(device.command + ["reverse", "--list"], text=True)
        require(port not in listing.split(), "Reverse port is already in use")
    with socket.socket() as available:
        available.bind((bind, args.port))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = private_directory(ROOT / "diagnostics" / (stamp + "-"+args.transport+"-app-probe-" + uuid.uuid4().hex[:8]))
    report = {"serial": device.serial, "sdk": device.props.get("ro.build.version.sdk"),
              "passed": False, "results": {}, "checks": {}, "cleanup": {},
              "transport":args.transport,"wifi_route":wifi_route,"apk_sha256":apk_hashes,
              "limits": ["USB loopback does not test Wi-Fi" if args.transport=="usb" else
                         "Private LAN traffic does not establish application Internet/DNS, roaming or sustained throughput"]}
    installed, reversed_port = [], False
    server = None
    server_output = (directory / "server.txt").open("w")

    def command(arguments, timeout=60):
        return subprocess.run(device.command + arguments, check=True, capture_output=True,
                              text=True, timeout=timeout)

    def cleanup_command(arguments):
        try:
            command(arguments, timeout=30)
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    try:
        server = subprocess.Popen(["python3", str(ROOT / "scripts/probe_server.py"),
            "--bind",bind,"--port", str(args.port), "--log", str(directory / "requests.jsonl")]
            +(["--allowed-peer",tablet_address] if tablet_address else []),
            stdout=server_output, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            require(server.poll() is None, "Probe server exited")
            try:
                with socket.create_connection((bind, args.port), timeout=1):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise ValueError("Probe server did not start")
        for package, apk in PACKAGES.items():
            installed.append(package)
            # Android 17's streamed Package Installer sessions are unreliable on this
            # legacy device and can hang after repeated probe runs.  Keep this probe
            # consistent with the rest of the qualification harness by staging the
            # complete APK before asking Package Installer to commit it.
            command(["install", "--no-streaming",
                     str(ROOT / "artifacts/device-validation" / apk)], timeout=120)
        if args.transport=="usb":
            reversed_port = True
            command(["reverse", "--no-rebind", port, port])
        # A unique URL prevents old logcat entries from satisfying a new run.
        endpoint = f"http://{bind}:{args.port}/payload?run={uuid.uuid4().hex}"
        report["endpoint"] = endpoint
        for package in PACKAGES:
            device.shell("am broadcast -f 0x20 -n " + package +
                         "/org.tabs3.validation.ProbeReceiver --es url " + shlex.quote(endpoint),
                         check=True)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            log = command(["logcat", "-d", "-s", "TabS3Probe:I", "*:S"]).stdout
            (directory / "logcat.txt").write_text(log)
            for line in log.splitlines():
                if "{" not in line:
                    continue
                try:
                    item = json.loads(line[line.index("{"):])
                except ValueError:
                    continue
                if item.get("package") in PACKAGES and item.get("endpoint") == endpoint:
                    report["results"][item["package"]] = item
            if len(report["results"]) == 2:
                break
            time.sleep(1)
        require(len(report["results"]) == 2, "Both probe results were not received")
        net, blocked = (report["results"][name] for name in PACKAGES)
        requests_file = directory / "requests.jsonl"
        require(requests_file.is_file(),
                "ADB reverse accepted the mapping but no HTTP request reached the host; "
                "this legacy adbd can retain stale reverse state after a prior probe, so "
                "reboot the tablet and rerun the qualification profile")
        requests = [json.loads(line) for line in requests_file.read_text().splitlines()]
        report["checks"] = {
            "internet_http": bool(net.get("internet_permission") and net.get("http_success")
                                  and net.get("body_bytes") == 262144
                                  and net.get("ordinary_permission_expectation_met")),
            "no_internet_denied": bool(not blocked.get("internet_permission", True)
                                       and not blocked.get("http_success", True)
                                       and blocked.get("permission_denied")
                                       and blocked.get("ordinary_permission_expectation_met")),
            "uid_accounting": bool(net.get("traffic_stats_available")
                                   and net.get("rx_delta", 0) > 0 and net.get("tx_delta", 0) > 0),
            "server_requests": bool(len(requests) == 1
                                    and requests[0]["probe"]["package"] == "org.tabs3.validation.net"
                                    and requests[0]["peer"]==(tablet_address or "127.0.0.1")
                                    and requests[0].get("write_completed")),
        }
        failed = [name for name, passed in report["checks"].items() if not passed]
        require(not failed, args.transport+" app checks failed: " + ", ".join(failed))
        report["passed"] = True
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        if reversed_port:
            report["cleanup"]["reverse_removed"] = cleanup_command(["reverse", "--remove", port])
        for package in installed:
            report["cleanup"][package] = cleanup_command(["uninstall", package])
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
        if server is not None:
            report["cleanup"]["server_stopped"] = server.poll() is not None
        server_output.close()
        if not all(report["cleanup"].values()):
            report["passed"] = False
            report.setdefault("error", "Probe cleanup was incomplete; inspect report")
        (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print("Report: " + str(directory / "report.json"), flush=True)
    require(all(report["cleanup"].values()), "Probe cleanup was incomplete; inspect report")
    print(args.transport+" HTTP, INTERNET permission and UID accounting checks passed; temporary apps removed")


if __name__ == "__main__":
    main()

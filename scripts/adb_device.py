"""Shared ADB selection and SM-T820 checks for the read-only collection tools."""
import pathlib
import re
import subprocess


class AdbDeviceNotReady(ValueError):
    """The pinned transport connected before its identity properties were ready."""


class AdbDevice:
    def __init__(self, serial=None):
        listing = subprocess.check_output(["adb", "devices"], text=True, timeout=10)
        states = dict(row.split()[:2] for row in listing.splitlines()[1:]
                      if len(row.split()) >= 2)
        devices = [name for name, state in states.items() if state in ("device", "recovery")]
        if serial is None:
            if not devices:
                if states:
                    observed = ", ".join(f"{name} ({state})" for name, state in states.items())
                    raise ValueError("No authorized ADB device is ready: " + observed)
                raise ValueError(
                    "The selected ADB server sees no devices. Run 'sh scripts/device.sh devices'. "
                    "If host 'adb devices' sees the tablet, set TAB_S3_ADB_BACKEND=host "
                    "and rerun 'sh scripts/device.sh start'.")
            if len(devices) > 1:
                raise ValueError("Multiple authorized ADB devices are connected; select the tablet with --serial")
            serial = devices[0]
        if serial not in devices:
            raise AdbDeviceNotReady("The selected ADB device is " + states.get(serial, "not listed by this ADB server"))
        self.serial = serial
        self.command = ["adb", "-s", serial]
        self.properties = self.shell("getprop", check=True).stdout
        props = dict(re.findall(r"^\[([^\]]+)\]: \[(.*)\]$", self.properties, re.M))
        models = [props.get(name, "") for name in (
            "ro.product.model", "ro.product.vendor.model", "ro.product.system.model")]
        codenames = [props.get(name, "") for name in (
            "ro.product.device", "ro.build.product", "ro.product.vendor.device")]
        if not any(models) and not any(codenames):
            raise AdbDeviceNotReady("ADB connected but model/variant properties are not ready")
        if "gts3llte" in codenames or "SM-T825" in models:
            raise ValueError("LTE SM-T825 is not this build's target")
        if "gts3lwifi" not in codenames and "SM-T820" not in models:
            raise ValueError("The connected device is not identified as SM-T820/gts3lwifi")
        self.props = props
        self.recovery = bool(props.get("ro.twrp.version"))

    def shell(self, command, timeout=60, check=False):
        return subprocess.run(self.command + ["shell", command], text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout, check=check)

    def pull(self, source, destination, timeout=120):
        return subprocess.run(self.command + ["pull", source, str(destination)],
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout)

    def require_recovery_root(self):
        if not self.recovery or self.shell("id -u", check=True).stdout.strip() != "0":
            raise ValueError("This operation requires the existing TWRP with its root ADB shell")


def private_directory(path):
    path = pathlib.Path(path)
    path.mkdir(parents=True, exist_ok=False, mode=0o700)
    return path

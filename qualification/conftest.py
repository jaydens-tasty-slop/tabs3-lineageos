import os
import json
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def install_probe(device, result_root, package, apk, label):
    from device_smoke_common import file_hash
    build = json.loads((apk.parent / "build.json").read_text())
    if file_hash(apk) != build["apk_sha256"]:
        pytest.fail(label + " diagnostic APK differs from its build record")
    preexisting = bool(device.shell("pm path " + package).stdout.strip())
    log = result_root / (label + "-probe-install.log")
    install_args = ["install", "--no-streaming"]
    if preexisting:
        install_args.append("-r")
    try:
        completed = subprocess.run(device.command + install_args + [str(apk)],
                                   text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=180)
        output = completed.stdout
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        output += "\nTIMEOUT after 180 seconds\n"
        log.write_text(output)
        pytest.fail(label + " probe install timed out; see " + log.name)
    log.write_text(output)
    if completed.returncode or "Success" not in output:
        pytest.fail(label + " probe install failed; see " + log.name)
    return not preexisting


def remove_probe(device, result_root, package, label):
    completed = subprocess.run(device.command + ["uninstall", package], text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=60)
    (result_root / (label + "-probe-uninstall.log")).write_text(completed.stdout)
    if completed.returncode or "Success" not in completed.stdout:
        pytest.fail(label + " probe cleanup failed; see uninstall log")


def pytest_addoption(parser):
    parser.addoption("--serial", help="ADB serial; omitted only when exactly one device is authorized")
    parser.addoption("--result-root", required=True, help="Existing private result directory")
    parser.addoption("--provision-widevine", action="store_true",
                     help="Allow one HTTPS Widevine provisioning request if required")


@pytest.fixture(scope="session")
def serial(pytestconfig):
    sys.path.insert(0, str(ROOT / "scripts"))
    from adb_device import AdbDevice
    device = AdbDevice(pytestconfig.getoption("serial"))
    if device.recovery:
        pytest.fail("Android must be booted; recovery is not a valid qualification target")
    if device.props.get("ro.build.version.sdk") != "37":
        pytest.fail("Android 17 / SDK 37 is required")
    if device.props.get("sys.boot_completed") != "1":
        pytest.fail("Android has not completed boot")
    return device.serial


@pytest.fixture(scope="session", autouse=True)
def preserve_usb_stay_awake(serial):
    """Keep a normally unlocked screen awake across the complete test session."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from adb_device import AdbDevice
    device = AdbDevice(serial)
    original = device.shell("settings get global stay_on_while_plugged_in", check=True).stdout.strip()
    if original != "null" and re.fullmatch(r"[0-7]", original) is None:
        pytest.fail("Unexpected USB stay-awake setting: " + original)
    try:
        device.shell("settings put global stay_on_while_plugged_in 2", check=True)
        if device.shell("settings get global stay_on_while_plugged_in", check=True).stdout.strip() != "2":
            pytest.fail("Could not enable USB stay-awake for qualification")
        yield
    finally:
        command = ("settings delete global stay_on_while_plugged_in" if original == "null"
                   else "settings put global stay_on_while_plugged_in " + original)
        restored = device.shell(command)
        actual = device.shell("settings get global stay_on_while_plugged_in").stdout.strip()
        if restored.returncode != 0 or actual != original:
            pytest.fail("Could not restore USB stay-awake setting after qualification")


@pytest.fixture(scope="session")
def result_root(pytestconfig):
    raw = pathlib.Path(pytestconfig.getoption("result_root")).absolute()
    expected = (ROOT / "diagnostics").resolve()
    try:
        relative = raw.relative_to(expected)
    except ValueError:
        pytest.fail("Result root must be under diagnostics/")
    cursor = expected
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            pytest.fail("Result root must not contain symlink components")
    path = raw.resolve()
    if not path.is_relative_to(expected) or not path.is_dir():
        pytest.fail("Result root must be a real directory under diagnostics/")
    (path / "logs").mkdir(mode=0o700)
    return path


@pytest.fixture(scope="session")
def media_probe_app(serial, result_root):
    sys.path.insert(0, str(ROOT / "scripts"))
    from adb_device import AdbDevice
    device = AdbDevice(serial)
    package = "org.tabs3.validation.media"
    apk = ROOT / "artifacts/device-media-validation/tabs3-media-probe.apk"
    installed_here = install_probe(device, result_root, package, apk, "media")
    try:
        yield
    finally:
        if installed_here:
            remove_probe(device, result_root, package, "media")


@pytest.fixture(scope="session")
def camera_probe_app(serial, result_root):
    sys.path.insert(0, str(ROOT / "scripts"))
    from adb_device import AdbDevice
    device = AdbDevice(serial)
    package = "org.tabs3.validation.cameracontrols"
    apk = ROOT / "artifacts/device-camera-controls/tabs3-camera-controls.apk"
    installed_here = install_probe(device, result_root, package, apk, "camera")
    try:
        yield
    finally:
        if installed_here:
            remove_probe(device, result_root, package, "camera")


@pytest.fixture
def run_probe(request, serial, result_root, pytestconfig):
    def run(script, *arguments, timeout=900):
        command = [sys.executable, str(ROOT / "scripts" / script), "--serial", serial,
                   *map(str, arguments)]
        if script == "device_media_probe.py" and pytestconfig.getoption("provision_widevine"):
            command.append("--provision-widevine")
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        log = result_root / "logs" / (request.node.name + ".log")
        try:
            completed = subprocess.run(command, cwd=ROOT, env=environment, text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       timeout=timeout)
            output = completed.stdout
        except subprocess.TimeoutExpired as error:
            output = error.stdout or ""
            if isinstance(output, bytes):
                output = output.decode(errors="replace")
            output += "\nTIMEOUT after " + str(timeout) + " seconds\n"
            log.write_text(output)
            pytest.fail(f"{script} timed out; log={log}")
        log.write_text(output)
        if completed.returncode:
            tail = "\n".join(completed.stdout.splitlines()[-60:])
            pytest.fail(f"{script} exited {completed.returncode}; log={log}\n{tail}")
        return log
    return run

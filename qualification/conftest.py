import os
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def install_probe(device, result_root, package, apk, label):
    from device_smoke_common import file_hash
    build = json.loads((apk.parent / "build.json").read_text())
    if file_hash(apk) != build["apk_sha256"]:
        pytest.fail(label + " diagnostic APK differs from its build record")
    if device.shell("pm path " + package).stdout.strip():
        return False
    log = result_root / (label + "-probe-install.log")
    try:
        completed = subprocess.run(device.command + ["install", "--no-streaming", str(apk)],
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
    return True


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
def run_probe(request, serial, result_root):
    def run(script, *arguments, timeout=900):
        command = [sys.executable, str(ROOT / "scripts" / script), "--serial", serial,
                   *map(str, arguments)]
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

#!/usr/bin/env python3
"""Build or validate every locally generated payload used by the public suite."""
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FULL = ROOT / "artifacts/device-media-fixtures-full-v1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(script, *arguments):
    subprocess.run([sys.executable, str(ROOT / "scripts" / script), *arguments],
                   cwd=ROOT, check=True)


def fixture_set_current():
    if not FULL.is_dir() or FULL.is_symlink():
        return False
    try:
        manifest = json.loads((FULL / "manifest.json").read_text())
    except (OSError, ValueError):
        return False
    if manifest.get("generator_sha256") != digest(ROOT / "scripts/generate_media_fixtures.py"):
        return False
    cases = manifest.get("cases", [])
    if len(cases) != 19:
        return False
    return all((FULL / item["file"]).is_file() and
               digest(FULL / item["file"]) == item["sha256"] for item in cases)


def apk_current(directory, name):
    try:
        record = json.loads((directory / "build.json").read_text())
        apk = directory / name
        sources = record["sources"]
        return (apk.is_file() and not apk.is_symlink() and digest(apk) == record["apk_sha256"]
                and all((ROOT / source).is_file() and digest(ROOT / source) == expected
                        for source, expected in sources.items()))
    except (OSError, KeyError, ValueError):
        return False


def network_apks_current():
    directory = ROOT / "artifacts/device-validation"
    try:
        record = json.loads((directory / "build.json").read_text())
        entries = record["apks"]
        if {item["file"] for item in entries} != {
                "tabs3-probe-net.apk", "tabs3-probe-noinet.apk"}:
            return False
        if not all((directory / item["file"]).is_file()
                   and digest(directory / item["file"]) == item["sha256"]
                   for item in entries):
            return False
        return all((ROOT / source).is_file()
                   and digest(ROOT / source) == expected
                   for source, expected in record["sources"].items())
    except (OSError, KeyError, ValueError):
        return False


def main():
    run("build_smoke_payloads.py")
    if fixture_set_current():
        print("Full 19-case media fixture set is current; skipped", flush=True)
    elif FULL.exists():
        raise ValueError("Full media fixture set is stale; archive it before rebuilding")
    else:
        run("generate_media_fixtures.py", "--output", str(FULL))
    if network_apks_current():
        print("Network permission payloads are current; skipped", flush=True)
    else:
        run("build_validation_payloads.py")
    io = ROOT / "artifacts/device-io-validation"
    if apk_current(io, "tabs3-io-probe.apk"):
        print("I/O payload is current; skipped", flush=True)
    else:
        run("build_io_payload.py")
    camera = ROOT / "artifacts/device-camera-controls"
    if apk_current(camera, "tabs3-camera-controls.apk"):
        print("Camera2 lifecycle payload is current; skipped", flush=True)
    else:
        run("build_camera_controls_payload.py")
    print("Qualification payloads are ready", flush=True)


if __name__ == "__main__":
    main()

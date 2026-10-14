#!/usr/bin/env python3
"""Build browser media and fetch signed F-Droid APKs for the app profile."""
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MEDIA = ROOT / "artifacts/device-media-stress-fixtures-v1"
EXPECTED = {
    "avc-high-1080p60-moving", "avc-high-2160p30-moving",
    "hevc-main-1080p60-moving", "hevc-main-2160p30-moving",
    "hevc-main10-1080p30-moving",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current():
    try:
        manifest = json.loads((MEDIA / "manifest.json").read_text())
        cases = manifest["cases"]
        return ({item["name"] for item in cases} == EXPECTED
                and all((MEDIA / item["file"]).is_file()
                        and not (MEDIA / item["file"]).is_symlink()
                        and digest(MEDIA / item["file"]) == item["sha256"]
                        for item in cases))
    except (OSError, KeyError, ValueError):
        return False


def main():
    if current():
        print("Browser stress media is current; skipped", flush=True)
    elif MEDIA.exists():
        raise ValueError("Existing browser media is incomplete or changed; archive it before rebuilding")
    else:
        subprocess.run([sys.executable, str(ROOT / "scripts/generate_media_stress_fixtures.py"),
                        "--output", str(MEDIA)], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/fetch_fdroid_payloads.py")],
                   cwd=ROOT, check=True)
    print("Browser/app payloads are ready", flush=True)


if __name__ == "__main__":
    main()

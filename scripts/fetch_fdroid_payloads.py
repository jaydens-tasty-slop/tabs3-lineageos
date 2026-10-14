#!/usr/bin/env python3
"""Fetch F-Droid test APKs through the repository's signed index."""
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "artifacts/fdroid-apps"
REPO = "https://f-droid.org/repo"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current():
    try:
        manifest = json.loads((OUTPUT / "manifest.json").read_text())
        packages = manifest["packages"]
        return (manifest["complete"] is True and len(packages) == 4
                and all((OUTPUT / item["file"]).is_file()
                        and not (OUTPUT / item["file"]).is_symlink()
                        and digest(OUTPUT / item["file"]) == item["sha256"]
                        and item["signature_verified"] is True
                        and item["signed_index_hash_verified"] is True
                        for item in packages))
    except (OSError, KeyError, ValueError):
        return False


def download(url, target):
    subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                    "--proto", "=https", "--tlsv1.2", "--retry", "2",
                    "--max-time", "300", "--output", str(target), url], check=True)


def main():
    if current():
        print("Verified F-Droid payload set is current; skipped", flush=True)
        return
    if OUTPUT.exists():
        raise ValueError("Existing artifacts/fdroid-apps is incomplete or changed; archive it before retrying")
    (ROOT / "state").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fdroid-index-", dir=ROOT / "state") as raw:
        temporary = pathlib.Path(raw)
        entry = temporary / "entry.jar"
        index = temporary / "index-v2.json"
        download(REPO + "/entry.jar", entry)
        download(REPO + "/index-v2.json", index)
        subprocess.run([sys.executable, str(ROOT / "scripts/prepare_fdroid_apps.py"),
                        "--output", str(OUTPUT), "--entry", str(entry),
                        "--index", str(index), "--sdk", "37"], cwd=ROOT, check=True)
    if not current():
        raise ValueError("F-Droid payload verification did not produce a complete set")


if __name__ == "__main__":
    main()

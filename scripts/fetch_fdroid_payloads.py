#!/usr/bin/env python3
"""Fetch F-Droid test APKs through the repository's signed index."""
import hashlib
import json
import datetime
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "artifacts/fdroid-apps"
REPO = "https://f-droid.org/repo"
EXPECTED_PACKAGES = {
    "org.fdroid.fdroid", "org.mozilla.fennec_fdroid", "com.kgurgul.cpuinfo",
    "net.tlfoxhuman.droidstress", "de.baumann.browser",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current(directory=OUTPUT):
    try:
        manifest = json.loads((directory / "manifest.json").read_text())
        packages = manifest["packages"]
        return (manifest["complete"] is True
                and {item["package"] for item in packages} == EXPECTED_PACKAGES
                and all((directory / item["file"]).is_file()
                        and not (directory / item["file"]).is_symlink()
                        and digest(directory / item["file"]) == item["sha256"]
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
    (ROOT / "state").mkdir(exist_ok=True)
    reuse = None
    if OUTPUT.exists():
        old = json.loads((OUTPUT / "manifest.json").read_text())
        old_packages = old["packages"]
        reusable = (old.get("complete") is True
                    and {item["package"] for item in old_packages} < EXPECTED_PACKAGES
                    and all((OUTPUT / item["file"]).is_file()
                            and not (OUTPUT / item["file"]).is_symlink()
                            and digest(OUTPUT / item["file"]) == item["sha256"]
                            and item["signature_verified"] is True
                            and item["signed_index_hash_verified"] is True
                            for item in old_packages))
        if not reusable:
            raise ValueError("Existing artifacts/fdroid-apps is incomplete or changed; archive it before retrying")
        reuse = OUTPUT
    with tempfile.TemporaryDirectory(prefix="fdroid-index-", dir=ROOT / "state") as raw:
        temporary = pathlib.Path(raw)
        entry = temporary / "entry.jar"
        index = temporary / "index-v2.json"
        destination = OUTPUT if reuse is None else ROOT / "artifacts/fdroid-apps-next"
        if destination.exists():
            raise ValueError("Stale artifacts/fdroid-apps-next exists; inspect it before retrying")
        download(REPO + "/entry.jar", entry)
        download(REPO + "/index-v2.json", index)
        command = [sys.executable, str(ROOT / "scripts/prepare_fdroid_apps.py"),
                   "--output", str(destination), "--entry", str(entry),
                   "--index", str(index), "--sdk", "37"]
        if reuse is not None:
            command.extend(["--reuse-from", str(reuse)])
        subprocess.run(command, cwd=ROOT, check=True)
    if not current(destination):
        raise ValueError("F-Droid payload verification did not produce a complete set")
    if reuse is not None:
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive = ROOT / "state" / ("fdroid-apps-four-package-" + stamp)
        OUTPUT.rename(archive)
        try:
            destination.rename(OUTPUT)
        except BaseException:
            archive.rename(OUTPUT)
            raise
        print("Expanded the verified payload set; prior exact files are hard-linked in "
              + str(archive.relative_to(ROOT)), flush=True)


if __name__ == "__main__":
    main()

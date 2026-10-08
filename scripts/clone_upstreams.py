#!/usr/bin/env python3
"""Keep complete Git clones of the requested device sources for later forks."""
import concurrent.futures
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPOSITORIES = [
    ("awesometic/android_device_samsung_gts3l-common", "device-common"),
    ("awesometic/android_device_samsung_gts3llte", "device-lte"),
    ("awesometic/android_device_samsung_gts3lwifi", "device-wifi"),
    ("awesometic/android_kernel_samsung_msm8996", "kernel"),
    ("awesometic/proprietary_vendor_samsung", "vendor-samsung"),
    ("LineageOS/android", "lineage-manifest"),
    ("awesometic/android-ota-provider", "ota-provider"),
    ("awesometic/android_device_samsung_gts3lwifi-twrp", "twrp-wifi"),
]


def clone(entry):
    repository, directory = entry
    target = ROOT / "upstream" / directory
    url = f"https://github.com/{repository}.git"
    if (target / ".git").is_dir():
        print(f"Already cloned: {repository}", flush=True)
    else:
        subprocess.run(["git", "clone", url, str(target)], check=True)
    return repository


if __name__ == "__main__":
    (ROOT / "upstream").mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for repository in pool.map(clone, REPOSITORIES):
            print(f"Cloned: {repository}", flush=True)

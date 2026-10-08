#!/usr/bin/env python3
"""Apply the exported port only to clean matching base checkouts."""
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
index = json.loads((ROOT / "patches/index.json").read_text())
lock = ROOT / index["base_manifest"]
if hashlib.sha256(lock.read_bytes()).hexdigest() != index["base_manifest_sha256"]:
    raise SystemExit("Base manifest checksum does not match the patch snapshot")

for change in index["changes"]:
    project = ROOT / "android" / change["path"]
    patch = ROOT / "patches" / change["patch"]
    if hashlib.sha256(patch.read_bytes()).hexdigest() != change["sha256"]:
        raise SystemExit(f"Patch checksum mismatch: {patch}")
    prefix = ["git", "-C", str(project)]
    already = subprocess.run(prefix + ["apply", "--reverse", "--check", str(patch)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if already.returncode == 0:
        print("Already applied: " + change["path"])
        continue
    head = subprocess.check_output(prefix + ["rev-parse", "HEAD"]).decode().strip()
    if head != change["base"]:
        raise SystemExit("Checkout does not match pinned base: " + change["path"])
    if subprocess.check_output(prefix + ["status", "--porcelain"]):
        raise SystemExit("Refusing to overwrite changes in " + change["path"])
    subprocess.run(prefix + ["apply", "--check", str(patch)], check=True)
    branch = "tabs3/lineage-23.2"
    exists = subprocess.run(prefix + ["show-ref", "--verify", "--quiet", "refs/heads/" + branch])
    if exists.returncode == 0:
        subprocess.run(prefix + ["checkout", branch], check=True)
        current = subprocess.check_output(prefix + ["rev-parse", "HEAD"]).decode().strip()
        if current != change["base"]:
            raise SystemExit("Existing fork branch does not match the base: " + change["path"])
    else:
        subprocess.run(prefix + ["checkout", "-b", branch], check=True)
    subprocess.run(prefix + ["apply", str(patch)], check=True)
    print("Applied: " + change["path"])

#!/usr/bin/env python3
"""Export changes relative to the immutable source lock, without modifying Git indexes."""
import concurrent.futures
import hashlib
import json
import os
import pathlib
import subprocess
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
ANDROID = pathlib.Path(os.environ.get("TAB_S3_ANDROID_DIR", ROOT / "android")).resolve()
LOCK = ROOT / "manifests/base-source-lock.xml"
OUTPUT = ROOT / "patches"
OUTPUT.mkdir(exist_ok=True)

# These pinned checkouts contain materialized LFS objects. Without the clean
# filter, Git silently exports unchanged APKs as enormous binary changes.
lfs_project = ANDROID / "external/chromium-webview/prebuilt/arm64"
lfs_filter = subprocess.run(["git", "-C", str(lfs_project), "config", "--get", "filter.lfs.clean"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
lfs_version = subprocess.run(["git", "lfs", "version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if lfs_filter.returncode != 0 or not lfs_filter.stdout.strip() or lfs_version.returncode != 0:
    raise SystemExit("Git LFS and its clean filter are required to export these checkouts. "
                     "Run export_port.py in the configured Podman build/device tools image.")


def git(project, *args):
    return subprocess.run(["git", "-C", str(project), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def export(attributes):
    path = attributes.get("path", attributes["name"])
    project = ANDROID / path
    base = attributes["revision"]
    git(project, "merge-base", "--is-ancestor", base, "HEAD")
    patch = git(project, "diff", "--binary", "--full-index", base)
    untracked = git(project, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    files = []
    for name in sorted(n for n in untracked if n):
        relative = name.decode()
        result = subprocess.run(["git", "diff", "--no-index", "--binary", "--full-index",
                                 "--", "/dev/null", relative], cwd=project,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode not in (0, 1):
            raise RuntimeError(result.stderr.decode())
        patch += result.stdout
        files.append(relative)
    if not patch:
        return None
    name = path.replace("/", "__") + ".patch"
    (OUTPUT / name).write_bytes(patch)
    branch = subprocess.run(["git", "-C", str(project), "symbolic-ref", "--short", "-q", "HEAD"],
                            stdout=subprocess.PIPE).stdout.decode().strip()
    remotes = git(project, "remote").decode().splitlines()
    urls = {remote: git(project, "remote", "get-url", remote).decode().strip()
            for remote in remotes}
    return {"path": path, "upstream_name": attributes["name"], "base": base,
            "head": git(project, "rev-parse", "HEAD").decode().strip(),
            "branch": branch or None, "remotes": urls, "patch": name,
            "sha256": hashlib.sha256(patch).hexdigest(), "untracked_files": files}


projects = [p.attrib for p in ET.parse(LOCK).getroot().findall("project")]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    changes = sorted((result for result in pool.map(export, projects) if result),
                     key=lambda result: result["path"])
report = {"base_manifest": "manifests/base-source-lock.xml",
          "base_manifest_sha256": hashlib.sha256(LOCK.read_bytes()).hexdigest(),
          "source_projects": len(projects), "changes": changes,
          "scope": "Source snapshot only; build and tablet validation reported separately."}
(OUTPUT / "index.json").write_text(json.dumps(report, indent=2) + "\n")
print(f"Exported {len(changes)} changed projects from {len(projects)} pinned Git clones")
for change in changes:
    print(change["path"])

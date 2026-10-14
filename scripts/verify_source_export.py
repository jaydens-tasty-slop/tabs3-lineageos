#!/usr/bin/env python3
"""Check each exported patch against its pinned Git tree using private indexes."""
import hashlib
import json
import os
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
ANDROID = pathlib.Path(os.environ.get("TAB_S3_ANDROID_DIR", ROOT / "android")).resolve()


def main():
    snapshot = json.loads((ROOT / "patches/index.json").read_text())
    lock = ROOT / snapshot["base_manifest"]
    assert hashlib.sha256(lock.read_bytes()).hexdigest() == snapshot["base_manifest_sha256"]
    checked = []
    with tempfile.TemporaryDirectory(prefix="source-export-", dir=ROOT / "state") as fixture:
        for number, change in enumerate(snapshot["changes"]):
            patch = ROOT / "patches" / change["patch"]
            assert hashlib.sha256(patch.read_bytes()).hexdigest() == change["sha256"]
            environment = os.environ.copy()
            environment["GIT_INDEX_FILE"] = str(pathlib.Path(fixture) / str(number))
            command = ["git", "-C", str(ANDROID / change["path"])]

            def git(*args):
                return subprocess.check_output(command + list(args), env=environment)

            git("read-tree", change["base"])
            git("apply", "--cached", "--check", str(patch))
            git("apply", "--cached", str(patch))
            git("apply", "--cached", "--reverse", "--check", str(patch))
            tree = git("write-tree").decode().strip()
            git("apply", "--cached", "--reverse", str(patch))
            restored = git("write-tree").decode().strip()
            expected = git("rev-parse", change["base"] + "^{tree}").decode().strip()
            assert restored == expected, "Patch reversal did not restore " + change["path"]
            git("read-tree", "HEAD")
            git("add", "--all")
            current = git("write-tree").decode().strip()
            assert tree == current, "Export differs from current source tree: " + change["path"]
            head_tree = git("rev-parse", "HEAD^{tree}").decode().strip()
            checked.append({"project": change["path"], "base": change["base"],
                            "patch_sha256": change["sha256"], "result_tree": tree,
                            "matches_current_source": True,
                            "all_changes_committed": current == head_tree})
            print("Patch round trip passed: " + change["path"], flush=True)
    report = {"status": "passed", "base_manifest_sha256": snapshot["base_manifest_sha256"],
              "projects_checked": checked, "hardware_tested": False,
              "scope": "Pinned Git tree patch application and reversal; no build or boot claim."}
    (ROOT / "research/source-export-verification.json").write_text(
        json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()

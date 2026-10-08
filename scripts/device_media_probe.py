#!/usr/bin/env python3
"""Run ordinary-app codec, GPU and WebView diagnostics over the pinned ADB transport."""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import shlex
import subprocess
import time
import uuid

from adb_device import AdbDevice, private_directory
from device_smoke_common import file_hash, require

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = "org.tabs3.validation.media"
ACTIVITY = PACKAGE + "/" + PACKAGE + ".MainActivity"
MIMES = {"avc": "video/avc", "hevc": "video/hevc", "mpeg4": "video/mp4v-es",
         "mpeg2": "video/mpeg2", "h263": "video/3gpp", "vp8": "video/x-vnd.on2.vp8",
         "vp9": "video/x-vnd.on2.vp9", "aac": "audio/mp4a-latm", "mp3": "audio/mpeg",
         "flac": "audio/flac", "vorbis": "audio/vorbis", "opus": "audio/opus"}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--suite", choices=("inventory", "gpu", "webview", "audio-route", "decode", "encode", "all"), default="all")
    parser.add_argument("--case", action="append", help="Limit decoding to these fixture names")
    parser.add_argument("--fixtures", type=pathlib.Path, default=ROOT / "artifacts/device-media-fixtures-v2")
    parser.add_argument("--keep-app", action="store_true", help="Keep this diagnostic package for follow-up probes")
    args = parser.parse_args()
    device = AdbDevice(args.serial)
    require(not device.recovery and device.props.get("ro.build.version.sdk") == "36"
            and device.props.get("sys.boot_completed") == "1", "Requires this tablet booted into Android 16")
    require(device.shell("am get-started-user-state 0", check=True).stdout.strip() == "RUNNING_UNLOCKED",
            "Unlock Android user 0 with its normal PIN/pattern after reboot before running app probes")
    payloads = ROOT / "artifacts/device-media-validation"
    apk = payloads / "tabs3-media-probe.apk"
    build = json.loads((payloads / "build.json").read_text())
    require(file_hash(apk) == build["apk_sha256"], "Diagnostic APK hash differs from its build record")
    fixtures = args.fixtures.resolve()
    require(fixtures.is_relative_to(ROOT / "artifacts"), "Use workspace diagnostic fixtures")
    manifest = json.loads((fixtures / "manifest.json").read_text())
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = private_directory(ROOT / "diagnostics" / (stamp + "-media-" + args.suite + "-" + uuid.uuid4().hex[:8]))
    (directory / "fixture-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    report = {"serial": args.serial, "suite": args.suite, "created_utc": stamp, "apk_sha256": build["apk_sha256"],
              "fixture_manifest_sha256": file_hash(fixtures / "manifest.json"), "results": [], "errors": [],
              "limits": ["Short generated clear clips do not establish secure playback, DRM licenses, HDR display or sustained throughput",
                         "Audio MediaCodec selection does not establish DSP offload or physical speaker output",
                         "No credentials, personal media or microphone audio are collected"]}
    installed_here = False
    staged = False
    target_dir = None
    staged_files = []
    existing_matching_app = False

    def adb(arguments, timeout=60, check=True):
        return subprocess.run(device.command + arguments, capture_output=True, text=True, timeout=timeout, check=check)

    def write_report():
        (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    def invoke(command, label, extra=None, timeout=120):
        filename = label + "-" + uuid.uuid4().hex[:8] + ".json"
        adb(["shell", "am", "force-stop", PACKAGE])
        shell = "am start -W -n " + ACTIVITY + " --es command " + shlex.quote(command) + " --es output " + shlex.quote(filename)
        for key, value in (extra or {}).items():
            shell += " --es " + shlex.quote(key) + " " + shlex.quote(value)
        result = device.shell(shell, timeout=30)
        (directory / (label + "-launch.txt")).write_text(result.stdout + result.stderr)
        require(result.returncode == 0 and "Error:" not in result.stdout, "Probe activity could not start")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            observed = adb(["exec-out", "run-as", PACKAGE, "cat", "files/" + filename], timeout=10, check=False)
            # exec-out can return host status zero while remote cat has no file yet.
            # Only a complete app JSON report satisfies this wait.
            if observed.returncode == 0 and observed.stdout.lstrip().startswith("{"):
                item = json.loads(observed.stdout)
                (directory / (label + ".json")).write_text(json.dumps(item, indent=2) + "\n")
                adb(["shell", "run-as", PACKAGE, "rm", "files/" + filename])
                return item
            time.sleep(1)
        log = adb(["logcat", "-b", "all", "-d", "-v", "threadtime", "-t", "10000"], check=False)
        (directory / (label + "-timeout-logcat.txt")).write_text(log.stdout + log.stderr)
        adb(["shell", "am", "force-stop", PACKAGE], check=False)
        return {"command": command, "passed": False, "error": "No completed JSON report before host deadline"}

    try:
        lookup = device.shell("pm path " + PACKAGE)
        require(lookup.returncode in (0, 1) and not lookup.stderr.strip(), "Package lookup failed")
        path = lookup.stdout.strip()
        if path:
            paths = [line.removeprefix("package:") for line in path.splitlines()]
            require(len(paths) == 1 and paths[0].startswith("/data/app/"), "Unexpected existing diagnostic package")
            before = device.shell("sha256sum " + shlex.quote(paths[0]), check=True).stdout.split()[0]
            require(before == build["apk_sha256"], "Existing diagnostic has different bytes; remove it explicitly before replacing")
            existing_matching_app = True
        else:
            adb(["install", "--no-streaming", str(apk)], timeout=120)
            installed_here = True
        report["framework_before"] = device.shell("pidof system_server; cat /proc/sys/kernel/random/boot_id", check=True).stdout
        if args.suite in ("inventory", "decode", "encode", "all"):
            inventory = invoke("inventory", "inventory")
            report["inventory"] = inventory
            report["results"].append({"name": "inventory", "passed": inventory.get("passed") is True})
            codecs = inventory.get("codecs", [])
            present = {item["name"] for item in codecs}
            report["missing_expected_vendor_components"] = [item for item in manifest["expected_vendor_codecs"] if item["name"] not in present]
        else:
            codecs = []
        if args.suite in ("gpu", "all"):
            item = invoke("gpu", "gpu")
            report["results"].append({"name": "gpu", **item})
        if args.suite in ("webview", "all"):
            item = invoke("webview", "webview", timeout=40)
            report["results"].append({"name": "webview", **item})
        if args.suite in ("audio-route", "all"):
            item = invoke("audio_route", "audio-route", timeout=30)
            report["results"].append({"name": "audio-route", **item})
        write_report()
        if args.suite == "encode":
            # Run this suite in the media image: host FFmpeg independently verifies
            # every encoded frame and color samples from actual device output.
            subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
            for mime in ("video/avc", "video/hevc"):
                candidates = [codec for codec in codecs if codec["encoder"] and codec["hardware_accelerated"]
                              and any(t["mime"] == mime for t in codec["types"])]
                if not candidates:
                    report["results"].append({"name": mime, "passed": False, "error": "No advertised hardware encoder"})
                for component in candidates:
                    label = "encode-" + component["name"].replace(".", "_")
                    item = invoke("encode", label, {"codec": component["name"], "mime": mime})
                    item["name"] = label
                    if item.get("passed"):
                        name = item["encoded_file"]
                        require(pathlib.PurePath(name).name == name and name.endswith(".mp4"), "Unexpected encoded output path")
                        output_file = directory / (label + ".mp4")
                        raw = subprocess.run(device.command + ["exec-out", "run-as", PACKAGE, "cat", "files/" + name],
                                             check=True, capture_output=True, timeout=30).stdout
                        require(len(raw) > 128, "Short encoded file transfer")
                        output_file.write_bytes(raw)
                        item["encoded_sha256"] = hashlib.sha256(raw).hexdigest()
                        ffprobe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(output_file)],
                                                 check=True, capture_output=True, text=True)
                        probe = json.loads(ffprobe.stdout)
                        (directory / (label + "-ffprobe.json")).write_text(json.dumps(probe, indent=2) + "\n")
                        stream = probe["streams"][0]
                        pixels_raw = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(output_file),
                            "-frames:v", "1", "-vf", "scale=128:128", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
                            check=True, capture_output=True).stdout
                        require(len(pixels_raw) == 128*128*3, "Short independently decoded reference")
                        pixels = []
                        for x, y in ((32,96), (96,96), (32,32), (96,32)):
                            at = (y*128+x)*3;pixels.append(list(pixels_raw[at:at+3]))
                        expected = [[0,0,255], [255,255,255], [255,0,0], [0,255,0]]
                        error = max(abs(pixels[i][j]-expected[i][j]) for i in range(4) for j in range(3))
                        item["independently_decoded_pixels"] = pixels
                        item["pixel_max_error"] = error
                        item["ffprobe_decoded_frames"] = int(stream["nb_read_frames"])
                        item["passed"] = item["hardware_accelerated"] and error <= 12 and item["ffprobe_decoded_frames"] == 30
                        device.shell("run-as " + PACKAGE + " rm files/" + shlex.quote(name), check=True)
                    report["results"].append(item);write_report()
                    print(label + ": " + str(item.get("passed")), flush=True)
        if args.suite in ("decode", "all"):
            selected = [case for case in manifest["cases"] if not args.case or case["name"] in args.case]
            require(not args.case or set(args.case) == {case["name"] for case in selected}, "Unknown fixture case")
            target_dir = "/data/local/tmp/tabs3-media-" + uuid.uuid4().hex[:12]
            listing = device.shell("ls -d " + target_dir)
            require(listing.returncode != 0, "Staging directory already exists; refusing to replace it")
            device.shell("mkdir -m 0755 " + target_dir, check=True)
            staged = True
            for case in selected:
                file = fixtures / case["file"]
                require(file.parent == fixtures and file.is_file() and not file.is_symlink()
                        and file_hash(file) == case["sha256"], "Fixture path/checksum failed")
                adb(["push", str(file), target_dir + "/" + file.name])
                staged_files.append(file.name)
                device.shell("chmod 0644 " + target_dir + "/" + shlex.quote(file.name), check=True)
                prefix = case["name"].split("-")[0]
                mime = MIMES[prefix]
                candidates = [codec for codec in codecs if not codec["encoder"] and codec["hardware_accelerated"]
                              and not codec["name"].endswith(".secure")
                              and any(t["mime"] == mime for t in codec["types"])]
                components = ["default"] + [codec["name"] for codec in candidates]
                if "main10" in case["name"]:
                    # HEVC Main10 is profile 2 in the public SDK.
                    components = [codec["name"] for codec in candidates if any(p["profile"] == 2 for t in codec["types"] if t["mime"] == mime for p in t.get("profiles", []))]
                    if not components:
                        report["results"].append({"name": case["name"], "status": "not_advertised", "passed": None,
                                                  "reason": "No hardware HEVC Main10 profile advertised"});write_report();continue
                for component in components:
                    label = case["name"] + "-" + component.replace(".", "_")
                    item = invoke("decode", label, {"input": target_dir + "/" + file.name, "codec": component})
                    item["name"] = label
                    item["requested_component"] = component
                    item["fixture_sha256"] = case["sha256"]
                    if case["kind"] == "video" and item.get("passed"):
                        expected = case["reference_pixels_gl_origin"]
                        errors = []
                        for frame in item.get("rendered_samples", []):
                            errors.append(max(abs(frame["pixels"][i][j] - expected[i][j]) for i in range(4) for j in range(3)))
                        item["pixel_max_error"] = max(errors) if errors else None
                        item["pixel_reference_passed"] = bool(errors and max(errors) <= case["pixel_max_error"])
                        item["fixture_frame_count_passed"] = item.get("output_frames") == case["frames"]
                        item["passed"] = item["pixel_reference_passed"] and item["fixture_frame_count_passed"]
                        if candidates and component == "default":
                            item["default_hardware_selected"] = item.get("hardware_accelerated") is True
                            item["passed"] &= item["default_hardware_selected"]
                    elif case["kind"] == "audio" and item.get("passed"):
                        item["tone_frequency_passed"] = abs(item.get("estimated_frequency_hz", 0) - 440) < 10
                        item["pcm_duration_passed"] = abs(item["pcm_samples"] / item["channels"] / item["sample_rate"] - 2) < .2
                        item["passed"] &= item["tone_frequency_passed"] and item["pcm_duration_passed"]
                    report["results"].append(item)
                    write_report()
                    print(label + ": " + str(item.get("passed")) + "; selected=" + str(item.get("component")), flush=True)
        report["framework_after"] = device.shell("pidof system_server; cat /proc/sys/kernel/random/boot_id").stdout
        report["framework_unchanged"] = report["framework_after"] == report["framework_before"]
        report["passed"] = bool(report["results"]) and all(item.get("passed") is not False for item in report["results"]) and report["framework_unchanged"]
        if args.suite in ("decode", "all"):
            report["passed"] &= not any(not item["secure"] for item in report.get("missing_expected_vendor_components", []))
    except BaseException as error:
        report["passed"] = False;report["errors"].append(str(error));raise
    finally:
        cleanup = {"passed": True, "steps": {}}

        def cleanup_step(name, action):
            try:
                result = action()
                if hasattr(result, "returncode") and result.returncode != 0:
                    raise RuntimeError("command returned " + str(result.returncode))
                cleanup["steps"][name] = True
            except BaseException as error:
                cleanup["passed"] = False
                cleanup["steps"][name] = False
                report["errors"].append("Cleanup " + name + ": " + str(error))

        if installed_here or existing_matching_app:
            cleanup_step("force_stop", lambda: device.shell("am force-stop " + PACKAGE, check=True))
        if staged:
            # Remove only files pushed into the unique directory created by this run.
            for filename in staged_files:
                cleanup_step("staged_file_" + filename, lambda filename=filename: device.shell(
                    "rm -f " + target_dir + "/" + shlex.quote(filename), check=True))
            cleanup_step("staging_directory", lambda: device.shell("rmdir " + target_dir, check=True))
        if installed_here and not args.keep_app:
            def uninstall_probe():
                result = adb(["uninstall", PACKAGE], check=False)
                if result.returncode != 0 or "Failure" in result.stdout:
                    raise RuntimeError(result.stdout.strip() or result.stderr.strip() or "uninstall failed")
                report["probe_removed"] = True
                return result
            cleanup_step("probe_uninstall", uninstall_probe)
        elif installed_here and args.keep_app:
            report["probe_retained_by_request"] = True
        elif existing_matching_app:
            report["probe_retained_existing"] = True
            cleanup["steps"]["probe_package"] = True
        def capture_logcat():
            log = adb(["logcat", "-b", "all", "-d", "-v", "threadtime", "-t", "30000"], check=False)
            if log.returncode != 0:
                raise RuntimeError(log.stderr.strip() or "logcat capture failed")
            (directory / "logcat.txt").write_text(log.stdout + log.stderr)
            return log
        cleanup_step("logcat_capture", capture_logcat)
        report["cleanup"] = cleanup
        if not cleanup["passed"]:
            report["passed"] = False
        write_report()
        print("Media evidence: " + str(directory / "report.json"), flush=True)


    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

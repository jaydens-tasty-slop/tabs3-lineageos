#!/usr/bin/env python3
"""Build a one-shot arm64 sleep clock using existing Android tools in Podman."""
import json
import pathlib
import subprocess

from device_smoke_common import file_hash, require

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    source = ROOT / "device-validation/native/sleep_clock.c"
    clang = ROOT / "android/prebuilts/clang/host/linux-x86/clang-r563880c/bin/clang"
    bionic = ROOT / "android/out/soong/.intermediates/bionic/libc"
    begin = bionic / "crtbegin_dynamic/android_arm64_armv8-a/crtbegin_dynamic.o"
    end = bionic / "crtend_android/android_arm64_armv8-a/crtend_android.o"
    libc = bionic / "libc/android_arm64_armv8-a_shared/libc.so"
    inputs = (source, clang, begin, end, libc, pathlib.Path(__file__))
    for path in inputs:
        require(path.is_file() and not path.is_symlink(),
                "Missing regular Android build input: " + str(path.relative_to(ROOT)))
    hashes = {str(path.relative_to(ROOT)): file_hash(path) for path in inputs}
    output = ROOT / "artifacts/device-sleep-clock"
    require(not output.is_symlink(), "Refusing linked payload directory")
    binary = output / "sleep-clock"
    record_path = output / "build.json"
    if output.exists():
        record = json.loads(record_path.read_text())
        require(record.get("inputs") == hashes and binary.is_file()
                and not binary.is_symlink() and file_hash(binary) == record.get("sha256"),
                "Existing sleep clock is stale; move artifacts/device-sleep-clock aside")
        print("Sleep clock is current; skipped")
        return
    output.mkdir(mode=0o700)
    command = [str(clang), "--target=aarch64-linux-android36", "-O2", "-Wall", "-Wextra",
               "-Werror", "-ffreestanding", "-fPIE", "-pie", "-nostdlib",
               "-Wl,--dynamic-linker,/system/bin/linker64", "-Wl,-z,relro,-z,now",
               "-Wl,--no-undefined", str(begin), str(source), str(libc), str(end),
               "-o", str(binary)]
    subprocess.run(command, check=True)
    data = binary.read_bytes()
    require(data[:6] == b"\x7fELF\x02\x01" and int.from_bytes(data[18:20], "little") == 183,
            "Expected arm64 Android ELF")
    record_path.write_text(json.dumps({"sha256": file_hash(binary), "inputs": hashes,
        "command": command, "scope": "One-shot CLOCK_MONOTONIC/CLOCK_BOOTTIME; ordinary UID 2000; no resident logger"},
        indent=2) + "\n")
    print("Built tiny sleep clock; no ROM build started")


if __name__ == "__main__":
    main()

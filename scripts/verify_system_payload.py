#!/usr/bin/env python3
"""Compare every full-OTA system write with the system image built from source."""
import argparse
import contextlib
import hashlib
import json
import pathlib
import shutil
import struct
import subprocess
import tempfile
import zipfile

from verify_ota import SYSTEM_LIMIT, image_prefix, require

ROOT = pathlib.Path(__file__).resolve().parent.parent
BLOCK = 4096
CHUNK = 4 * 1024 * 1024


def decoder_tool(tools, name):
    candidates = [tools / name]
    repository = "build-tools" if name == "brotli" else "kernel-build-tools"
    candidates.extend(ROOT / "android/prebuilts" / repository / platform / "bin" / name
                      for platform in ("linux_musl-x86", "linux-x86"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ValueError("pinned image tool is missing: " + name)


def transfer_operations(text, image_bytes):
    rows = text.splitlines()
    require(len(rows) >= 4 and int(rows[0]) in (3, 4), "unsupported transfer list")
    require(int(rows[1]) > 0 and int(rows[2]) == int(rows[3]) == 0,
            "system payload is not a full OTA")
    operations, written = [], []
    writes_started = False
    count = 0
    for row in rows[4:]:
        fields = row.split()
        require(len(fields) == 2 and fields[0] in ("new", "zero", "erase"),
                "unexpected full OTA transfer operation")
        command = fields[0]
        numbers = list(map(int, fields[1].split(",")))
        require(numbers and numbers[0] > 0 and numbers[0] == len(numbers) - 1
                and numbers[0] % 2 == 0, "invalid transfer range count")
        ranges = list(zip(numbers[1::2], numbers[2::2]))
        require(all(0 <= start < end <= image_bytes // BLOCK for start, end in ranges),
                "system transfer range exceeds the built image")
        require(all(first[1] <= second[0] for first, second in zip(ranges, ranges[1:])),
                "overlapping or unordered ranges in a transfer command")
        if command == "erase":
            require(not writes_started, "erase operation follows system writes")
        else:
            writes_started = True
            count += sum(end - start for start, end in ranges)
        written.extend(ranges)
        operations.append((command, ranges))
    written.sort()
    require(all(first[1] <= second[0] for first, second in zip(written, written[1:])),
            "system transfer commands write overlapping blocks")
    require(count == int(rows[1]), "system transfer block count mismatch")
    return operations


def verify_system_payload(rom, image, tools=None):
    if tools is None:
        tools = ROOT / "android/out/host/linux-x86/bin"
    _, size = image_prefix(image)
    require(0 < size <= SYSTEM_LIMIT and size % BLOCK == 0, "invalid expanded system size")
    ROOT.joinpath("state").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="system-payload-", dir=ROOT / "state") as name:
        temporary = pathlib.Path(name)
        raw = image
        with image.open("rb") as source:
            sparse = source.read(4) == struct.pack("<I", 0xED26FF3A)
        if sparse:
            converter = decoder_tool(tools, "simg2img")
            raw = temporary / "system.raw.img"
            subprocess.run([str(converter), str(image), str(raw)], check=True)
            require(raw.stat().st_size == size, "simg2img expanded size mismatch")
        with zipfile.ZipFile(rom) as archive, contextlib.ExitStack() as stack:
            operations = transfer_operations(
                archive.read("system.transfer.list").decode(), size)
            payloads = [n for n in archive.namelist()
                        if n in ("system.new.dat", "system.new.dat.br")]
            require(len(payloads) == 1, "missing or ambiguous system data payload")
            require(archive.getinfo("system.patch.dat").file_size == 0,
                    "full system payload has an incremental patch")
            process = None
            if payloads[0].endswith(".br"):
                brotli = decoder_tool(tools, "brotli")
                compressed = temporary / "system.new.dat.br"
                with archive.open(payloads[0]) as source, compressed.open("wb") as destination:
                    shutil.copyfileobj(source, destination, CHUNK)
                error = stack.enter_context((temporary / "brotli-error.txt").open("w+b"))
                process = stack.enter_context(subprocess.Popen(
                    [str(brotli), "--decompress", "--stdout", str(compressed)],
                    stdout=subprocess.PIPE, stderr=error))
                data = process.stdout
            else:
                data = stack.enter_context(archive.open(payloads[0]))
            expected = stack.enter_context(raw.open("rb"))
            new_hash = hashlib.sha256()
            new_bytes = zero_bytes = 0
            try:
                for command, ranges in operations:
                    if command == "erase":
                        continue
                    for start, end in ranges:
                        expected.seek(start * BLOCK)
                        remaining = (end - start) * BLOCK
                        while remaining:
                            take = min(CHUNK, remaining)
                            reference = expected.read(take)
                            require(len(reference) == take, "truncated built system image")
                            if command == "new":
                                actual = data.read(take)
                                require(len(actual) == take, "truncated decoded OTA system data")
                                require(actual == reference,
                                        f"OTA system bytes differ at block {expected.tell() // BLOCK - take // BLOCK}")
                                new_hash.update(actual)
                                new_bytes += take
                            else:
                                require(not any(reference), "OTA zeroes nonzero system image data")
                                zero_bytes += take
                            remaining -= take
                require(data.read(1) == b"", "OTA system data has extra decoded bytes")
                if process:
                    result = process.wait(timeout=60)
                    error.seek(0)
                    require(result == 0, "Brotli decode failed: " + error.read().decode(errors="replace"))
            finally:
                if process and process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
    return {"matches_built_system": True, "expanded_system_bytes": size,
            "new_data_bytes": new_bytes, "zero_data_bytes": zero_bytes,
            "decoded_new_data_sha256": new_hash.hexdigest(),
            "scope": "All new and zero transfer ranges match the built image; no device writes."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=pathlib.Path)
    parser.add_argument("--system-image", type=pathlib.Path, required=True)
    parser.add_argument("--report", type=pathlib.Path, required=True)
    args = parser.parse_args()
    report = verify_system_payload(args.zip, args.system_image)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

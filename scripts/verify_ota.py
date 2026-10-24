#!/usr/bin/env python3
"""Offline SM-T820 OTA checks; a pass is not a hardware boot result."""
import argparse
import hashlib
import json
import pathlib
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib

BOOT_LIMIT = 79691776
SYSTEM_LIMIT = 4194304000
ALLOWED_PARTITIONS = {"boot", "system", "cache"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_device_tree(tree):
    require(len(tree) >= 40, "truncated device tree")
    magic, size, structure, strings_offset, _, version, _, _, strings_size, structure_size = \
        struct.unpack_from(">10I", tree)
    require(magic == 0xD00DFEED and size == len(tree) and version >= 17,
            "unsupported device tree header")
    require(structure + structure_size <= size and strings_offset + strings_size <= size,
            "invalid device tree sections")
    strings = tree[strings_offset:strings_offset + strings_size]
    offset, stack, nodes = structure, [], {}
    while offset + 4 <= structure + structure_size:
        token = struct.unpack_from(">I", tree, offset)[0]
        offset += 4
        if token == 1:
            end = tree.index(b"\x00", offset, structure + structure_size)
            stack.append(tree[offset:end].decode())
            offset = ((end + 4) // 4) * 4
        elif token == 2:
            require(stack, "unbalanced device tree node")
            stack.pop()
        elif token == 3:
            require(stack and offset + 8 <= structure + structure_size,
                    "invalid device tree property")
            length, name_offset = struct.unpack_from(">II", tree, offset)
            offset += 8
            require(offset + length <= structure + structure_size and name_offset < strings_size,
                    "device tree property exceeds its section")
            end = strings.index(b"\x00", name_offset)
            name = strings[name_offset:end].decode()
            path = "/" + "/".join(stack[1:])
            if path.startswith("/firmware/android") and name in (
                    "status", "compatible", "dev", "type", "mnt_flags", "fsmgr_flags"):
                nodes.setdefault(path, {})[name] = tree[offset:offset + length].rstrip(b"\x00").decode()
            offset = ((offset + length + 3) // 4) * 4
        elif token == 4:
            continue
        elif token == 9:
            require(not stack, "unclosed device tree node")
            break
        else:
            raise ValueError("unexpected device tree token")
    else:
        raise ValueError("device tree end marker is missing")
    root = "/firmware/android"
    require(nodes.get(root, {}).get("compatible") == "android,firmware"
            and nodes.get(root + "/fstab", {}).get("compatible") == "android,fstab",
            "device tree lacks the legacy first-stage fstab")
    system = nodes.get(root + "/fstab/system", {})
    require(system.get("status") in ("ok", "okay") and system.get("type") == "ext4"
            and system.get("dev") == "/dev/block/platform/soc/7464900.sdhci/by-name/system",
            "unexpected first-stage system mount")
    require(nodes.get(root + "/fstab/vendor", {}).get("status") == "disabled",
            "device tree requests a separate vendor partition")
    return {"system": system, "separate_vendor_partition": False}


def check_kernel(data):
    require(data.startswith(b"\x1f\x8b"), "kernel is not Image.gz-dtb")
    gzip = zlib.decompressobj(16 + zlib.MAX_WBITS)
    raw = gzip.decompress(data, 128 * 1024 * 1024)
    require(gzip.eof, "kernel gzip is invalid or exceeds 128 MiB")
    require(raw[56:60] == b"ARM\x64", "kernel is not a Linux arm64 Image")
    tail = gzip.unused_data
    trees = []
    mounts = []
    while tail:
        tail = tail.lstrip(b"\x00")
        if not tail:
            break
        require(len(tail) >= 40, "truncated appended device tree")
        magic, size = struct.unpack_from(">II", tail)
        require(magic == 0xD00DFEED and 40 <= size <= len(tail),
                "invalid appended device tree")
        trees.append(size)
        mounts.append(check_device_tree(tail[:size]))
        tail = tail[size:]
    require(len(trees) == 4, "kernel does not contain all four SM-T820 board device trees")
    version = re.search(rb"Linux version (3\.18\.140[^\x00\n]{0,240})", raw)
    require(version is not None, "kernel lacks the expected 3.18.140 version banner")
    return {"uncompressed_bytes": len(raw), "device_tree_bytes": trees,
            "first_stage_mounts": mounts,
            "version_banner": version.group(1).decode(errors="replace")}


def check_ramdisk(data):
    entries = {}
    repeated_directories = 0
    offset = 0
    while offset + 110 <= len(data):
        header = data[offset:offset + 110]
        require(header[:6] == b"070701", "invalid ramdisk cpio header")
        fields = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        mode, uid, gid, size, namesize = fields[1], fields[2], fields[3], fields[6], fields[11]
        start = offset + 110
        require(namesize > 0 and start + namesize <= len(data), "truncated cpio filename")
        name_data = data[start:start + namesize]
        require(name_data[-1:] == b"\x00", "unterminated cpio filename")
        name = name_data[:-1].decode().removeprefix("./")
        require(name and not name.startswith("/")
                and ".." not in pathlib.PurePosixPath(name).parts, "unsafe cpio filename")
        start = ((start + namesize + 3) // 4) * 4
        require(start + size <= len(data), "truncated cpio file")
        payload = data[start:start + size]
        offset = ((start + size + 3) // 4) * 4
        if name == "TRAILER!!!":
            require(size == 0 and not any(data[offset:]), "invalid cpio trailer or extra archive")
            break
        if name in entries:
            require(mode & 0o170000 == 0o040000
                    and entries[name][0] & 0o170000 == 0o040000 and not payload,
                    "duplicate ramdisk file: " + name)
            repeated_directories += 1  # mkbootfs can merge multiple directory roots.
        entries[name] = (mode, uid, gid, payload)
        if name.endswith(".rc"):
            require(not re.search(rb'(?m)^\s*service\s+\S+\s+[^\n]*install-recovery\.sh',
                                  payload), "automatic recovery updater in boot ramdisk: " + name)
    else:
        raise ValueError("ramdisk cpio trailer is missing")
    require("init" in entries, "boot ramdisk has no init entry")
    mode, uid, gid, payload = entries["init"]
    require(uid == gid == 0, "ramdisk init is not owned by root")
    if mode & 0o170000 == 0o100000:
        require(mode & 0o111, "ramdisk init is not executable")
        binary = check_installer(payload)
        require(binary["architecture"] == "arm64", "ramdisk init is not ARM64")
        init = {"kind": "static-arm64", "sha256": binary["sha256"]}
    elif mode & 0o170000 == 0o120000:
        require(payload == b"/system/bin/init", "unexpected ramdisk init symlink")
        init = {"kind": "system-init-symlink"}
    else:
        raise ValueError("unexpected ramdisk init file type")
    return {"entries": len(entries), "init": init,
            "repeated_directories": repeated_directories,
            "automatic_recovery_update_service": False}


def check_boot(data):
    require(len(data) >= 1632, "truncated Android boot header")
    require(len(data) <= BOOT_LIMIT, "boot image exceeds the SM-T820 partition")
    require(data.startswith(b"ANDROID!"), "boot image lacks Android boot magic")
    kernel_size, kernel_addr, ramdisk_size = struct.unpack_from("<III", data, 8)
    ramdisk_addr = struct.unpack_from("<I", data, 20)[0]
    second_size, _, tags_addr, page_size, version = struct.unpack_from("<IIIII", data, 24)
    require(version == 0, f"unexpected boot header version {version}")
    require(page_size == 4096, f"unexpected boot page size {page_size}")
    require(kernel_addr == 0x80008000, "unexpected Samsung kernel load address")
    require(ramdisk_addr == 0x82200000, "unexpected Samsung ramdisk load address")
    require(tags_addr == 0x82000000, "unexpected Samsung tags address")
    require(kernel_size > 0 and ramdisk_size > 0 and second_size == 0,
            "unexpected boot image layout")
    end = page_size + kernel_size
    require(end <= len(data), "truncated boot kernel")
    ramdisk_start = ((end + page_size - 1) // page_size) * page_size
    ramdisk_end = ramdisk_start + ramdisk_size
    padded_end = ((ramdisk_end + page_size - 1) // page_size) * page_size
    require(len(data) == padded_end + len(b"SEANDROIDENFORCE")
            and data[padded_end:] == b"SEANDROIDENFORCE",
            "truncated ramdisk, extra boot sections, or invalid Samsung footer")
    ramdisk = data[ramdisk_start:ramdisk_end]
    unpacker = zlib.decompressobj(16 + zlib.MAX_WBITS)
    unpacked = unpacker.decompress(ramdisk, 128 * 1024 * 1024)
    require(unpacker.eof and not unpacker.unused_data and unpacked.startswith(b"070701"),
            "boot ramdisk is not a complete gzip/newc archive")
    ramdisk_info = check_ramdisk(unpacked)
    boot_id = hashlib.sha1()
    for payload in (data[page_size:end], ramdisk, b""):
        boot_id.update(payload)
        boot_id.update(struct.pack("<I", len(payload)))
    boot_id.update(struct.pack("<I", 0))  # Samsung legacy v0 dt_size convention.
    require(data[576:596] == boot_id.digest(), "boot header payload hash mismatch")
    return {"bytes": len(data), "page_size": page_size, "header_version": version,
            "boot_id_style": "legacy-v0-dt-size", "ramdisk_bytes": ramdisk_size, "kernel_sha256":
            hashlib.sha256(data[page_size:end]).hexdigest(),
            "ramdisk": ramdisk_info,
            "kernel": check_kernel(data[page_size:end])}


def check_installer(data):
    require(len(data) >= 64 and data.startswith(b"\x7fELF"),
            "installer is not a complete ELF executable")
    elf_class = data[4]
    require(elf_class in (1, 2) and data[5] == 1, "unsupported installer ELF layout")
    machine = struct.unpack_from("<H", data, 18)[0]
    require((elf_class, machine) in ((1, 40), (2, 183)),
            "installer executable is not ARM/arm64")
    if elf_class == 2:
        offset = struct.unpack_from("<Q", data, 32)[0]
        size, count = struct.unpack_from("<HH", data, 54)
        minimum = 56
    else:
        offset = struct.unpack_from("<I", data, 28)[0]
        size, count = struct.unpack_from("<HH", data, 42)
        minimum = 32
    require(count > 0 and size >= minimum and offset + size * count <= len(data),
            "invalid installer program headers")
    for index in range(count):
        start = offset + size * index
        kind = struct.unpack_from("<I", data, start)[0]
        require(kind != 3, "installer needs a dynamic loader")
        if kind == 2:
            if elf_class == 2:
                table = struct.unpack_from("<Q", data, start + 8)[0]
                length = struct.unpack_from("<Q", data, start + 32)[0]
                entry, fmt = 16, "<QQ"
            else:
                table = struct.unpack_from("<I", data, start + 4)[0]
                length = struct.unpack_from("<I", data, start + 16)[0]
                entry, fmt = 8, "<II"
            require(table + length <= len(data) and length % entry == 0,
                    "invalid installer dynamic table")
            for current in range(table, table + length, entry):
                tag, value = struct.unpack_from(fmt, data, current)
                require(tag != 1, "installer needs a runtime shared library")
                if tag == 0:
                    break
    return {"architecture": "arm64" if machine == 183 else "arm",
            "static": True, "sha256": hashlib.sha256(data).hexdigest()}


def image_prefix(path, count=2048):
    """Read an image prefix without expanding a many-gigabyte sparse image."""
    with path.open("rb") as stream:
        header = stream.read(28)
        if header[:4] != struct.pack("<I", 0xED26FF3A):
            stream.seek(0)
            return stream.read(count), path.stat().st_size
        magic, major, minor, file_header, chunk_header, block_size, blocks, chunks, crc = \
            struct.unpack("<IHHHHIIII", header)
        require(major == 1 and file_header >= 28 and chunk_header >= 12,
                "unsupported sparse image header")
        stream.seek(file_header)
        output = bytearray()
        for _ in range(chunks):
            start = stream.tell()
            chunk = stream.read(chunk_header)
            require(len(chunk) == chunk_header, "truncated sparse image")
            kind, reserved, chunk_blocks, total = struct.unpack_from("<HHII", chunk)
            require(total >= chunk_header, "invalid sparse chunk size")
            expanded = chunk_blocks * block_size
            take = min(expanded, count - len(output))
            if kind == 0xCAC1:
                output.extend(stream.read(take))
            elif kind == 0xCAC2:
                fill = stream.read(4)
                require(len(fill) == 4, "truncated sparse fill")
                output.extend((fill * ((take + 3) // 4))[:take])
            elif kind == 0xCAC3:
                output.extend(b"\x00" * take)
            elif kind != 0xCAC4:
                raise ValueError(f"unknown sparse chunk {kind:#x}")
            stream.seek(start + total)
            if len(output) >= count:
                break
        require(len(output) >= count, "image lacks the requested prefix")
        return bytes(output), blocks * block_size


def ext4_supported_mask(kernel, category):
    source = (kernel / "fs/ext4/ext4.h").read_text().replace("\\\n", " ")
    definitions = dict(re.findall(r"(?m)^#define\s+(\w+)\s+([^\n]+)", source))
    name = f"EXT4_FEATURE_{category}_SUPP"
    require(name in definitions, f"cannot find kernel {name}")
    names = re.findall(r"EXT4_FEATURE_\w+", definitions[name])
    mask = 0
    for flag in names:
        match = re.match(r"\s*(0x[0-9a-fA-F]+|[0-9]+)\b", definitions.get(flag, ""))
        require(match is not None, f"cannot resolve kernel feature {flag}")
        mask |= int(match.group(1), 0)
    return mask


def check_ext4(prefix, kernel):
    require(len(prefix) >= 2048, "truncated ext4 superblock")
    sb = prefix[1024:2048]
    require(struct.unpack_from("<H", sb, 56)[0] == 0xEF53, "image is not ext4")
    features = dict(zip(("COMPAT", "INCOMPAT", "RO_COMPAT"),
                        struct.unpack_from("<III", sb, 92)))
    for category in ("INCOMPAT", "RO_COMPAT"):
        unsupported = features[category] & ~ext4_supported_mask(kernel, category)
        require(unsupported == 0,
                f"ext4 uses features absent from kernel: {category} {unsupported:#x}")
    return features


def check_system(path, kernel):
    prefix, expanded_bytes = image_prefix(path)
    require(expanded_bytes <= SYSTEM_LIMIT, "system image exceeds the SM-T820 partition")
    return {"expanded_bytes": expanded_bytes, "ext4_features": check_ext4(prefix, kernel),
            "image_sha256": file_sha256(path)}


def check_apexes(system, kernel):
    apexes = sorted((system / "apex").glob("*.apex"))
    require(apexes and not list((system / "apex").glob("*.capex")),
            "packed uncompressed APEX payloads are missing or compressed APEX is present")
    checked = []
    for path in apexes:
        with zipfile.ZipFile(path) as archive:
            require("apex_pubkey" in archive.namelist(), f"missing APEX verity key: {path.name}")
            with archive.open("apex_payload.img") as payload:
                features = check_ext4(payload.read(2048), kernel)
            checked.append({"apex": path.name, "ext4_features": features})
    return checked


def check_ota(path, expected_sdk, device="gts3lwifi"):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "duplicate ZIP entries")
        require(not any(n.startswith("/") or ".." in pathlib.PurePosixPath(n).parts
                        for n in names), "unsafe ZIP entry path")
        require(archive.testzip() is None, "ZIP CRC failure")
        require("payload.bin" not in names, "A/B payload is incompatible with this target")
        metadata = archive.read("META-INF/com/android/metadata").decode()
        values = dict(line.split("=", 1) for line in metadata.splitlines() if "=" in line)
        require(values.get("pre-device") == device, f"OTA metadata is not {device}")
        require(values.get("ota-type") == "BLOCK", "OTA is not a non-A/B block installer")
        require(values.get("ota-wipe") != "yes", "OTA requests a data wipe")
        require(values.get("ota-retrofit-dynamic-partitions") != "yes",
                "OTA requests repartitioning")
        require(values.get("post-sdk-level") == str(expected_sdk),
                f"OTA does not contain the expected Android SDK {expected_sdk}")
        script = archive.read("META-INF/com/google/android/updater-script").decode()
        require(re.search(r'assert\([\s\S]{0,2000}getprop\("ro\.product\.device"\)\s*==\s*"' + device + '"',
                          script) is not None, f"missing explicit {device} device assertion")
        partitions = set(re.findall(r"/by-name/([A-Za-z0-9_-]+)", script))
        require(partitions and partitions <= ALLOWED_PARTITIONS,
                f"unexpected installer partition references: {sorted(partitions)}")
        require(not re.search(r'format\([^;]*"/data"', script), "installer formats user data")
        other = "gts3llte" if device == "gts3lwifi" else "gts3lwifi"
        require(other not in script, f"installer assertion also accepts {other}")
        require(not re.search(r'package_extract_file\("recovery\.img"\s*,', script),
                "installer writes a recovery image")
        require(not re.search(r'\b(?:update_dynamic_partitions|reboot_now|set_stage)\(', script),
                "installer changes partitions or uses multistage recovery flashing")
        executable = archive.read("META-INF/com/google/android/update-binary")
        installer = check_installer(executable)
        transfers = [n for n in names if n.endswith(".transfer.list")]
        require(transfers == ["system.transfer.list"],
                f"unexpected block image transfers: {transfers}")
        rows = archive.read(transfers[0]).decode().splitlines()
        require(len(rows) >= 4 and int(rows[0]) in (3, 4), "unsupported transfer list")
        require(int(rows[1]) > 0 and int(rows[2]) == int(rows[3]) == 0,
                "full OTA has no data blocks or requires incremental stashes")
        transferred = 0
        for row in rows[4:]:
            command, *arguments = row.split()
            if command in ("new", "erase", "zero"):
                ranges = list(map(int, arguments[0].split(",")))
                require(ranges[0] == len(ranges) - 1 and ranges[0] % 2 == 0,
                        "invalid block ranges")
                require(all(0 <= block <= SYSTEM_LIMIT // 4096 for block in ranges[1:]),
                        "installer writes beyond the system partition")
                pairs = list(zip(ranges[1::2], ranges[2::2]))
                require(all(start < end for start, end in pairs), "empty or reversed block range")
                require(all(previous[1] <= following[0]
                            for previous, following in zip(pairs, pairs[1:])),
                        "unordered or overlapping block ranges")
                if command in ("new", "zero"):
                    transferred += sum(end - start for start, end in pairs)
            else:
                raise ValueError(f"full OTA contains unexpected operation {command}")
        require(transferred == int(rows[1]), "transfer list block count mismatch")
        boot = check_boot(archive.read("boot.img"))
    digest = file_sha256(path)
    return {"zip": path.name, "sha256": digest, "metadata": values,
            "installer_partitions": sorted(partitions), "installer": installer, "boot": boot}


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=pathlib.Path)
    parser.add_argument("--system-image", type=pathlib.Path, required=True)
    parser.add_argument("--kernel-source", type=pathlib.Path, required=True)
    parser.add_argument("--kernel-image", type=pathlib.Path, required=True)
    parser.add_argument("--installed-system", type=pathlib.Path, required=True,
                        help="Build output system directory, to check installed init services")
    parser.add_argument("--report", type=pathlib.Path, required=True)
    parser.add_argument("--expected-sdk", type=int, default=37)
    parser.add_argument("--device", choices=("gts3lwifi", "gts3llte"), default="gts3lwifi")
    args = parser.parse_args()
    report = check_ota(args.zip, args.expected_sdk, args.device)
    require(report["boot"]["kernel_sha256"] == file_sha256(args.kernel_image),
            "ZIP kernel differs from the final built kernel payload")
    init_files = list((args.installed_system / "etc/init").rglob("*.rc"))
    init_files += list((args.installed_system / "vendor/etc/init").rglob("*.rc"))
    require(init_files, "cannot find installed init files to check recovery preservation")
    for path in init_files:
        require(not re.search(r'(?m)^\s*service\s+\S+\s+[^\n]*install-recovery\.sh',
                              path.read_text()), f"automatic recovery updater installed: {path}")
    report["automatic_recovery_update_service"] = False
    require((args.installed_system / "etc/vintf/compatibility_matrix.4.xml").is_file(),
            "Restored vendor FCM 4 contract is missing from the installed system")
    report["vendor_fcm4_contract_installed"] = True
    permissions = ET.parse(args.installed_system / "etc/permissions/platform.xml").getroot()
    internet = permissions.findall("permission[@name='android.permission.INTERNET']/group")
    require(any(group.get("gid") == "inet" for group in internet),
            "legacy kernel requires the INTERNET permission to grant the INET group")
    report["legacy_internet_permission_group_installed"] = True
    vendor = args.installed_system / "vendor"
    vibrator_fragment = ET.parse(vendor / "etc/vintf/manifest" /
                                 "android.hardware.vibrator-service.legacy.xml").getroot()
    vibrator = vibrator_fragment.find("hal[@format='aidl'][name='android.hardware.vibrator']")
    require(vibrator is not None and vibrator.findtext("version") == "2"
            and vibrator.findtext("fqname") == "IVibrator/default",
            "legacy vibrator AIDL v2 declaration is missing")
    require((vendor / "bin/hw/android.hardware.vibrator-service.legacy").is_file()
            and (vendor / "lib64/hw/vibrator.default.so").is_file(),
            "legacy vibrator service or ARM64 hardware module is missing")
    require(not (vendor / "bin/hw/android.hardware.vibrator@1.0-service").exists(),
            "obsolete HIDL vibrator service remains installed")
    report["legacy_vibrator_aidl_adapter_installed"] = True
    report["apex_filesystems"] = check_apexes(args.installed_system, args.kernel_source)
    report["system"] = check_system(args.system_image, args.kernel_source)
    from verify_system_payload import verify_system_payload
    report["system_payload"] = verify_system_payload(args.zip, args.system_image)
    report["hardware_tested"] = False
    report["scope"] = "Offline package checks only; hardware and boot remain unverified."
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    args.zip.with_suffix(".zip.sha256").write_text(
        f"{report['sha256']}  {args.zip.name}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, struct.error, zlib.error, zipfile.BadZipFile) as error:
        print(f"Verification failed: {error}", file=sys.stderr)
        sys.exit(1)

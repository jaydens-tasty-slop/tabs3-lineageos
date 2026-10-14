#!/usr/bin/env python3
"""Fail-closed ADB/key audit for a Tab S3 build source and ROM package.

This reads source configuration, staged target-files, the built System image,
Boot image, and OTA ZIP. It never mounts an image or writes to an input. The
report contains paths and hashes only, never key contents.
"""
import argparse
import hashlib
import json
import os
import posixpath
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess
import tempfile
import zipfile
import zlib

from verify_system_payload import verify_system_payload
from verify_ota import check_boot


ROOT = Path(__file__).resolve().parents[1]
SENSITIVE_NAMES = {"adb_keys", "adbkey", "adbkey.pub", "adbkey.private"}
TEXT_SUFFIXES = {".rc", ".prop", ".mk", ".bp", ".conf", ".sh", ".xml"}
CONFIG_SUFFIXES = {".rc", ".prop"}
PRIVATE_ARMOR = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")
ADB_KEY_ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:export\s+)?(?:ADB_VENDOR_KEYS|PRODUCT_ADB_KEYS)\s*(?:\+=|\?=|:=|=)\s*([^#\r\n]+)")
PROPERTY_OVERRIDE = re.compile(
    r"(?im)^\s*PRODUCT_DEFAULT_PROPERTY_OVERRIDES\s*(?:\+=|\?=|:=|=)\s*([^#\r\n]+)")
FORCED_SET_PROPERTY = re.compile(
    r"(?i)\bsetprop\s+(persist\.(?:sys|vendor)\.usb\.config|sys\.usb\.config)\s+([^\s#]+)")
INSECURE_SET_PROPERTY = re.compile(
    r"(?i)\bsetprop\s+(ro\.adb\.secure|ro\.secure|persist\.service\.adb\.enable|service\.adb\.root)\s+([^\s#]+)")
ADB_CONFIG_PROPERTY = re.compile(
    r"(?i)^\s*(persist\.(?:sys|vendor)\.usb\.config|sys\.usb\.config)\s*=\s*([^#\r\n]+)")
INSECURE_PROPERTY = re.compile(
    r"(?i)^\s*(ro\.adb\.secure|ro\.secure|persist\.service\.adb\.enable|service\.adb\.root)\s*=\s*([^#\r\n]+)")
ADB_ENABLED_PROPERTY = re.compile(r"(?i)^\s*adb_enabled\s*=\s*([^#\r\n]+)")
ADB_ENABLED_XML = re.compile(
    r"(?i)\bname\s*=\s*[\"']adb_enabled[\"'][^>]*\bvalue\s*=\s*[\"'](?:1|true|yes)[\"']")
PROPERTY_LINE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*=\s*([^\s#]*)")
ADB_INIT_BASENAME = "zz-gts3l-bringup-usb.rc"
MAX_CONFIG_BYTES = 4 * 1024 * 1024
MAX_RAMDISK_BYTES = 128 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_plain_tree(root):
    require(root.is_dir() and not root.is_symlink(), "Tree hash root must be a plain directory")
    records = []
    for path in walk_plain_tree(root, "tree hash input"):
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        mode = stat.S_IFMT(info.st_mode) | stat.S_IMODE(info.st_mode)
        if stat.S_ISLNK(info.st_mode):
            payload = os.readlink(path).encode("utf-8", errors="strict")
            kind = b"L"
        elif stat.S_ISREG(info.st_mode):
            payload = bytes.fromhex(sha256_file(path))
            kind = b"F"
        elif stat.S_ISDIR(info.st_mode):
            payload = b""
            kind = b"D"
        else:
            raise ValueError("Unsupported special file in target-files tree: " + relative)
        records.append((relative.encode("utf-8"), kind, mode, payload))
    digest = hashlib.sha256()
    for relative, kind, mode, payload in sorted(records, key=lambda row: row[0]):
        digest.update(kind)
        digest.update(struct.pack("<I", len(relative)))
        digest.update(relative)
        digest.update(struct.pack("<I", mode))
        digest.update(struct.pack("<Q", len(payload)))
        digest.update(payload)
    return digest.hexdigest()


def plain_file(path, label):
    require(path.is_file() and not path.is_symlink(), label + " must be a regular non-symlink file")
    return path


def clean_line(line):
    return line.split("#", 1)[0].strip()


def has_adb_function(value):
    tokens = re.split(r"[,\s\"']+", value.strip())
    return any(token.lower() == "adb" for token in tokens)


def has_insecure_adb_override(value):
    return bool(re.search(
        r"(?i)(?:ro\.adb\.secure|ro\.secure)\s*=\s*0\b|"
        r"(?:persist\.service\.adb\.enable|service\.adb\.root)\s*=\s*(?:1|true|yes)\b",
        value))


def inspect_config_bytes(data, relative_path, findings, properties=None):
    require(len(data) <= MAX_CONFIG_BYTES, "Configuration file exceeds size limit: " + relative_path)
    require(b"\x00" not in data, "Configuration file contains NUL bytes: " + relative_path)
    if PRIVATE_ARMOR.search(data):
        findings.append({"kind": "private_key_armor", "path": relative_path})
    text = data.decode("utf-8", errors="strict")
    if ADB_ENABLED_XML.search(text):
        findings.append({"kind": "adb_enabled_xml_setting", "path": relative_path})
    if relative_path.endswith(".rc") and Path(relative_path).name == ADB_INIT_BASENAME:
        findings.append({"kind": "forbidden_device_adb_init", "path": relative_path})
    for number, raw_line in enumerate(text.splitlines(), 1):
        line = clean_line(raw_line)
        if not line:
            continue
        match = FORCED_SET_PROPERTY.search(line)
        if match and has_adb_function(match.group(2)):
            findings.append({"kind": "forced_usb_adb_setprop", "path": relative_path,
                             "line": number, "property": match.group(1)})
        match = INSECURE_SET_PROPERTY.search(line)
        if match:
            name, value = match.groups()
            normalized = value.strip().lower()
            if ((name.lower() in ("ro.adb.secure", "ro.secure") and normalized == "0") or
                    (name.lower() in ("persist.service.adb.enable", "service.adb.root") and
                     normalized in ("1", "true", "yes"))):
                findings.append({"kind": "insecure_adb_setprop", "path": relative_path,
                                 "line": number, "property": name})
        match = ADB_CONFIG_PROPERTY.match(line)
        if match and has_adb_function(match.group(2)):
            findings.append({"kind": "usb_adb_config_property", "path": relative_path,
                             "line": number, "property": match.group(1),
                             "value": match.group(2).strip()})
        match = INSECURE_PROPERTY.match(line)
        if match:
            name, value = match.groups()
            normalized = value.strip().lower()
            if ((name.lower() in ("ro.adb.secure", "ro.secure") and normalized == "0") or
                    (name.lower() in ("persist.service.adb.enable", "service.adb.root") and
                     normalized in ("1", "true", "yes"))):
                findings.append({"kind": "insecure_adb_property", "path": relative_path,
                                 "line": number, "property": name})
        match = ADB_ENABLED_PROPERTY.match(line)
        if match and match.group(1).strip().lower() in ("1", "true", "yes"):
            findings.append({"kind": "adb_enabled_property", "path": relative_path,
                             "line": number})
        if properties is not None and relative_path.endswith(".prop"):
            match = PROPERTY_LINE.match(line)
            if match:
                properties.setdefault(match.group(1), []).append({
                    "path": relative_path, "line": number, "value": match.group(2)})
        for match in ADB_KEY_ASSIGNMENT.finditer(line):
            if match.group(1).strip().strip('"\''):
                findings.append({"kind": "adb_key_injection_variable", "path": relative_path,
                                 "line": number})
        for match in PROPERTY_OVERRIDE.finditer(line):
            value = match.group(1)
            override = re.search(
                r"(?i)(?:persist\.(?:sys|vendor)\.usb\.config|sys\.usb\.config)\s*=\s*([^\s]+)",
                value)
            if override and has_adb_function(override.group(1)):
                findings.append({"kind": "adb_property_override", "path": relative_path,
                                 "line": number})
            if has_insecure_adb_override(value):
                findings.append({"kind": "insecure_adb_property_override",
                                 "path": relative_path, "line": number})


def audit_release_properties(properties, findings, scope):
    """Require production ADB security properties, with no contradictory copy."""
    expected = {
        "ro.adb.secure": "1",
        "ro.secure": "1",
        "ro.debuggable": "0",
    }
    for name, wanted in expected.items():
        entries = properties.get(name, [])
        values = sorted({entry["value"] for entry in entries})
        if not entries or any(entry["value"] != wanted for entry in entries):
            findings.append({
                "kind": scope + "_release_adb_property_mismatch",
                "property": name,
                "expected_value": wanted,
                "observed_values": values,
            })


def walk_plain_tree(root, label):
    require(root.is_dir() and not root.is_symlink(), label + " must be a plain directory")
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        base = Path(current)
        for name in list(directories):
            item = base / name
            if item.is_symlink():
                directories.remove(name)
                yield item
        for name in files:
            yield base / name


def target_link_target(root, link):
    pending = link.relative_to(root).parts
    seen = set()
    hops = 0
    while pending:
        current = root
        restart = False
        for index, component in enumerate(pending):
            current = current / component
            try:
                mode = current.lstat().st_mode
            except FileNotFoundError:
                return None
            if stat.S_ISLNK(mode):
                hops += 1
                require(hops <= 40, "ADB key symlink loop in staged target tree")
                identity = current.relative_to(root).as_posix()
                require(identity not in seen, "ADB key symlink loop in staged target tree")
                seen.add(identity)
                raw = os.readlink(current)
                if raw.startswith("/"):
                    parts = list(PurePosixPath(raw).parts[1:])
                    # Target-files SYSTEM is usually the virtual Android
                    # /system root. Keep a real nested system/ directory when
                    # present; otherwise map absolute /system/... links back
                    # into the supplied tree.
                    if parts[:1] == ["system"] and not (root / "system").exists():
                        parts = parts[1:]
                    candidate = root.joinpath(*parts)
                else:
                    candidate = current.parent / raw
                normalized = Path(os.path.normpath(candidate))
                require(normalized == root or root in normalized.parents,
                        "ADB key symlink escapes the staged target tree: " + identity)
                remaining = pending[index + 1:]
                pending = normalized.relative_to(root).parts + remaining
                restart = True
                break
            if index + 1 < len(pending) and not stat.S_ISDIR(mode):
                return None
        if restart:
            continue
        return current, mode
    return root, root.lstat().st_mode


def audit_key_paths(root, paths, findings, scope):
    inspected = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            resolved = target_link_target(root, path)
            exists = resolved is not None
            target_mode = resolved[1] if resolved else None
            size = resolved[0].stat().st_size if resolved and stat.S_ISREG(target_mode) else None
            inspected.append({"scope": scope, "path": relative, "type": "symlink",
                              "target_exists": exists, "target_bytes": size})
            if not exists:
                continue
            if stat.S_ISREG(target_mode) and size == 0:
                continue
            findings.append({"kind": "adb_key_symlink_target_present", "scope": scope,
                             "path": relative})
        elif path.is_file() and not path.is_symlink():
            size = path.stat(follow_symlinks=False).st_size
            inspected.append({"scope": scope, "path": relative, "type": "regular",
                              "bytes": size})
            if size:
                findings.append({"kind": "nonempty_adb_key_file", "scope": scope,
                                 "path": relative, "bytes": size})
        else:
            findings.append({"kind": "unsupported_adb_key_path_type", "scope": scope,
                             "path": relative})
    return inspected


def audit_source(source_root):
    require(not source_root.is_symlink(), "Android source root may not be a symlink")
    source_root = source_root.resolve(strict=True)
    findings, scanned = [], 0
    roots = [source_root / "device/samsung/gts3l-common",
             source_root / "device/samsung/gts3lwifi",
             source_root / "vendor/samsung/gts3l-common",
             source_root / "vendor/samsung/gts3lwifi"]
    existing = [path for path in roots if path.exists()]
    require(len(existing) >= 2 and all(path.is_dir() and not path.is_symlink() for path in existing),
            "Expected Tab S3 source configuration roots are missing or unsafe")
    required_common = source_root / "device/samsung/gts3l-common"
    required_wifi = source_root / "device/samsung/gts3lwifi"
    require(required_common.is_dir() and required_wifi.is_dir(),
            "Both gts3l-common and gts3lwifi source trees are required")
    bringup_rc = required_common / "configs/bringup-usb.rc"
    require(not bringup_rc.exists() and not bringup_rc.is_symlink(),
            "Device-specific bringup-usb.rc remains in source")
    sensitive = []
    for root in existing:
        for path in walk_plain_tree(root, "Android device/vendor source"):
            name = path.name.lower()
            if name in SENSITIVE_NAMES:
                sensitive.append(path.relative_to(source_root).as_posix())
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            require(not path.is_symlink(), "Source configuration is a symlink")
            data = path.read_bytes()
            if len(data) > MAX_CONFIG_BYTES or b"\x00" in data:
                continue
            relative = path.relative_to(source_root).as_posix()
            before = len(findings)
            inspect_config_bytes(data, relative, findings)
            # The general source tree may contain documentation describing ADB.
            # Ignore comments, but an executable/config match always blocks.
            scanned += 1
            if len(findings) > before:
                pass
    if sensitive:
        findings.extend({"kind": "adb_key_named_source_file", "path": path} for path in sensitive)
    set_environment = [name for name in ("ADB_VENDOR_KEYS", "PRODUCT_ADB_KEYS")
                       if os.environ.get(name)]
    if set_environment:
        findings.extend({"kind": "adb_build_environment_override", "variable": name}
                        for name in set_environment)
    default_overrides = os.environ.get("PRODUCT_DEFAULT_PROPERTY_OVERRIDES", "")
    if default_overrides and (re.search(
            r"(?i)(?:persist\.(?:sys|vendor)\.usb\.config|sys\.usb\.config)\s*=\s*[^\s]*adb",
            default_overrides) or has_insecure_adb_override(default_overrides)):
        findings.append({"kind": "adb_build_environment_override",
                         "variable": "PRODUCT_DEFAULT_PROPERTY_OVERRIDES"})
    return {"source_roots": [path.relative_to(source_root).as_posix() for path in existing],
            "text_configs_scanned": scanned, "findings": findings}


def audit_target_files(target_root):
    require(not target_root.is_symlink(), "Target-files root may not be a symlink")
    target_root = target_root.resolve(strict=True)
    findings, scanned, key_paths, properties = [], 0, [], {}
    require(target_root.is_dir() and not target_root.is_symlink(),
            "Target-files root must be a plain directory")
    for path in walk_plain_tree(target_root, "target-files tree"):
        name = path.name.lower()
        if name == ADB_INIT_BASENAME:
            findings.append({"kind": "forbidden_device_adb_init",
                             "path": path.relative_to(target_root).as_posix()})
        if name in SENSITIVE_NAMES:
            key_paths.append(path)
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.stat(follow_symlinks=False).st_size > MAX_CONFIG_BYTES:
            continue
        relative = path.relative_to(target_root).as_posix()
        data = path.read_bytes()
        if b"\x00" in data:
            continue
        inspect_config_bytes(data, relative, findings, properties)
        scanned += 1
    key_inventory = audit_key_paths(target_root, key_paths, findings, "target-files")
    audit_release_properties(properties, findings, "target_files")
    release_properties = {}
    for name in ("ro.lineage.version", "ro.build.version.incremental", "ro.build.date.utc"):
        entries = properties.get(name, [])
        values = sorted({entry["value"] for entry in entries})
        if len(values) != 1 or not values[0]:
            findings.append({"kind": "target_files_release_property_not_unique",
                             "property": name, "observed_values": values})
        else:
            release_properties[name] = values[0]
    return {"text_configs_scanned": scanned,
            "key_paths": key_inventory,
            "release_properties": release_properties,
            "adb_properties": {name: values for name, values in sorted(properties.items())
                               if name in ("ro.adb.secure", "ro.debuggable", "ro.secure",
                                           "persist.sys.usb.config", "persist.vendor.usb.config",
                                           "sys.usb.config",
                                           "persist.service.adb.enable", "service.adb.root")},
            "findings": findings}


def ota_build_metadata(archive):
    member = "META-INF/com/android/metadata"
    require(member in archive.namelist(), "OTA has no Android build metadata member")
    data = archive.read(member)
    require(len(data) <= MAX_CONFIG_BYTES and b"\x00" not in data,
            "OTA build metadata is malformed or oversized")
    properties = {}
    for line in data.decode("utf-8", errors="strict").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            properties.setdefault(key, []).append(value)
    wanted = ("post-build", "post-build-incremental", "post-timestamp")
    result = {}
    for name in wanted:
        values = sorted(set(properties.get(name, [])))
        require(len(values) == 1 and values[0], "OTA metadata property is missing or duplicated: " + name)
        result[name] = values[0]
    return result


def run_debugfs(debugfs, raw_image, command):
    result = subprocess.run([str(debugfs), "-R", command, str(raw_image)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    output = result.stdout + b"\n" + result.stderr
    require(result.returncode == 0 and not re.search(
        rb"(?i)(?:file not found|not found by ext2_lookup|permission denied|"
        rb"could not open|no such file|ext2fs_open.*failed|error:)", output),
        "debugfs reported an error on a fixed read-only query")
    return result.stdout


def parse_debugfs_directory(output, directory):
    entries, dot_entries = [], set()
    for line in output.decode("utf-8", errors="strict").splitlines():
        if not line.startswith("/"):
            continue
        fields = line.split("/")
        require(len(fields) == 8 and fields[1].isdigit() and fields[3].isdigit() and
                fields[4].isdigit(), "Unexpected debugfs directory listing format")
        inode, mode, uid, gid = int(fields[1]), int(fields[2], 8), int(fields[3]), int(fields[4])
        name = fields[5]
        if not inode:
            require(mode == 0 and not name, "Unexpected empty debugfs directory slot")
            continue
        if name in (".", ".."):
            require(stat.S_ISDIR(mode), "Debugfs dot entry is not a directory")
            dot_entries.add(name)
            continue
        require(name and name not in (".", "..") and "/" not in name and "\x00" not in name,
                "Unsafe name in filesystem image")
        path = directory.rstrip("/") + "/" + name
        require(re.fullmatch(r"/[A-Za-z0-9_ ./@+,\[\]-]+", path) is not None,
                "Unsupported pathname in filesystem image: " + repr(path))
        entries.append({"path": path, "name": name, "mode": mode, "uid": uid, "gid": gid,
                        "size": int(fields[6]) if fields[6] else 0})
    require(dot_entries == {".", ".."},
            "Debugfs listing did not contain validated dot and dot-dot entries: " + directory)
    return entries


def debugfs_path(path):
    allowed = path == "/" or re.fullmatch(r"/[A-Za-z0-9_ ./@+,\[\]-]+", path) is not None
    require(path.startswith("/") and allowed and
            (path == "/" or all(component not in ("", ".", "..")
                                 for component in path.split("/")[1:])),
        "Unsafe path for fixed debugfs read query: " + repr(path))
    # Quotes are excluded by the whitelist above. Quoting prevents spaces or
    # debugfs command syntax from changing the fixed read-only operation.
    return '"' + path + '"'


def system_image_inventory(debugfs, image):
    entries, pending = {}, ["/"]
    while pending:
        directory = pending.pop()
        listing = run_debugfs(debugfs, image, "ls -p " + debugfs_path(directory))
        rows = parse_debugfs_directory(listing, directory)
        for row in rows:
            require(row["path"] not in entries, "Duplicate path in System image")
            entries[row["path"]] = row
            if stat.S_ISDIR(row["mode"]):
                pending.append(row["path"])
    return entries


def debugfs_symlink_target(debugfs, image, path):
    output = run_debugfs(debugfs, image, "stat " + debugfs_path(path)).decode("utf-8", errors="replace")
    match = re.search(r"(?m)^Fast link dest:\s*(.*?)\s*$", output)
    if match is None:
        return None
    target = match.group(1)
    if target.startswith('"'):
        require(len(target) >= 2 and target.endswith('"') and '"' not in target[1:-1],
                "Malformed quoted ADB-key symlink target")
        target = target[1:-1]
    else:
        require('"' not in target, "Malformed unquoted ADB-key symlink target")
    require(target and re.fullmatch(r"[A-Za-z0-9_ ./@+,\[\]-]+", target) is not None,
            "Unsupported ADB-key symlink target format")
    return target


def resolve_image_path(debugfs, image, inventory, link_path, raw_target):
    """Resolve a System-image symlink through every path component.

    Return (status, final_path, final_entry). Absolute /system/... targets are
    mapped to the image's root because this image is the Android /system FS.
    """
    seen_links = set()
    hops = 0
    if raw_target.startswith("/"):
        parts = list(PurePosixPath(raw_target).parts[1:])
        if parts[:1] == ["system"] and "/system" not in inventory:
            parts = parts[1:]
    else:
        parts = list(PurePosixPath(posixpath.join(
            posixpath.dirname(link_path), raw_target)).parts[1:])
    pending = parts
    while pending:
        current_parts = []
        restarted = False
        for index, component in enumerate(pending):
            if component in ("", "."):
                continue
            if component == "..":
                if not current_parts:
                    raise ValueError("ADB-key symlink escapes the System image")
                current_parts.pop()
                continue
            current_parts.append(component)
            current = "/" + "/".join(current_parts)
            entry = inventory.get(current)
            if entry is None:
                return "absent", current, None
            if stat.S_ISLNK(entry["mode"]):
                hops += 1
                require(hops <= 40, "ADB-key symlink chain exceeds the resolution limit")
                require(current not in seen_links, "ADB-key symlink loop in System image")
                seen_links.add(current)
                target = debugfs_symlink_target(debugfs, image, current)
                if target is None:
                    return "unresolved", current, entry
                if target.startswith("/"):
                    next_parts = list(PurePosixPath(target).parts[1:])
                    if next_parts[:1] == ["system"] and "/system" not in inventory:
                        next_parts = next_parts[1:]
                else:
                    next_parts = list(PurePosixPath(posixpath.join(
                        posixpath.dirname(current), target)).parts[1:])
                pending = next_parts + pending[index + 1:]
                restarted = True
                break
            if index + 1 < len(pending) and not stat.S_ISDIR(entry["mode"]):
                return "absent", current, None
        if restarted:
            continue
        final_path = "/" + "/".join(current_parts) if current_parts else "/"
        return "resolved", final_path, inventory.get(final_path)
    return "resolved", "/", None


def audit_system_image(system_image, tools_dir):
    require(not tools_dir.is_symlink(), "Android tools directory may not be a symlink")
    debugfs = plain_file(tools_dir / "debugfs_static", "debugfs_static")
    simg2img = plain_file(tools_dir / "simg2img", "simg2img")
    original_sha = sha256_file(system_image)
    with system_image.open("rb") as stream:
        sparse = stream.read(4) == struct.pack("<I", 0xED26FF3A)
    with tempfile.TemporaryDirectory(prefix="release-adb-system-") as temp_name:
        temp = Path(temp_name)
        raw = temp / "system.raw.img"
        if sparse:
            subprocess.run([str(simg2img), str(system_image), str(raw)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        else:
            raw = system_image
        inventory = system_image_inventory(debugfs, raw)
        findings, key_rows, properties = [], [], {}
        sensitive_paths = [row for row in inventory.values()
                           if row["name"].lower() in SENSITIVE_NAMES]
        for row in inventory.values():
            if row["name"] == ADB_INIT_BASENAME:
                findings.append({"kind": "forbidden_device_adb_init", "path": row["path"]})
        for row in sensitive_paths:
            target = debugfs_symlink_target(debugfs, raw, row["path"]) if stat.S_ISLNK(row["mode"]) else None
            key_record = {"path": row["path"], "type": stat.S_IFMT(row["mode"]),
                          "bytes": row["size"]}
            if stat.S_ISREG(row["mode"]) and row["size"]:
                findings.append({"kind": "nonempty_adb_key_file", "path": row["path"],
                                 "bytes": row["size"]})
            elif stat.S_ISLNK(row["mode"]):
                if target is None:
                    key_record["resolution"] = "unresolved"
                    findings.append({"kind": "adb_key_symlink_target_unresolved",
                                     "path": row["path"]})
                else:
                    status, resolved, target_entry = resolve_image_path(
                        debugfs, raw, inventory, row["path"], target)
                    key_record["symlink_target"] = target
                    key_record["resolution"] = status
                    if resolved is not None:
                        key_record["resolved_path"] = resolved
                    if target_entry is not None:
                        key_record["target_type"] = stat.S_IFMT(target_entry["mode"])
                        key_record["target_bytes"] = target_entry["size"]
                    if status == "unresolved":
                        findings.append({"kind": "adb_key_symlink_target_unresolved",
                                         "path": row["path"]})
                    elif (status == "resolved" and target_entry is not None and
                          stat.S_ISREG(target_entry["mode"]) and target_entry["size"] > 0):
                        findings.append({"kind": "adb_key_symlink_target_present",
                                         "path": row["path"]})
                    elif (status == "resolved" and target_entry is not None and
                          not stat.S_ISREG(target_entry["mode"])):
                        findings.append({"kind": "unsupported_adb_key_symlink_target_type",
                                         "path": row["path"]})
            elif not stat.S_ISREG(row["mode"]):
                findings.append({"kind": "unsupported_adb_key_path_type", "path": row["path"]})
            key_rows.append(key_record)

        config_count = 0
        for row in inventory.values():
            suffix = Path(row["path"]).suffix.lower()
            if suffix not in CONFIG_SUFFIXES or not stat.S_ISREG(row["mode"]):
                continue
            if row["size"] > MAX_CONFIG_BYTES:
                findings.append({"kind": "oversize_config_file", "path": row["path"]})
                continue
            data = run_debugfs(debugfs, raw, "cat " + debugfs_path(row["path"]))
            inspect_config_bytes(data, row["path"].lstrip("/"), findings, properties)
            config_count += 1
        audit_release_properties(properties, findings, "system")
        return {"sha256": original_sha, "sparse_input": sparse,
                "filesystem_paths_enumerated": len(inventory),
                "text_configs_scanned": config_count,
                "key_paths": key_rows,
                "adb_properties": {name: values for name, values in sorted(properties.items())
                                   if name in ("ro.adb.secure", "ro.debuggable", "ro.secure",
                                               "persist.sys.usb.config", "persist.vendor.usb.config",
                                               "sys.usb.config",
                                               "persist.service.adb.enable", "service.adb.root")},
                "findings": findings}


def boot_ramdisk(image):
    require(len(image) >= 1632 and image.startswith(b"ANDROID!"),
            "Boot image is not a supported Android legacy image")
    kernel_size, _, ramdisk_size = struct.unpack_from("<III", image, 8)
    second_size, _, _, page_size, version = struct.unpack_from("<IIIII", image, 24)
    require(version == 0 and page_size == 4096 and second_size == 0 and kernel_size and ramdisk_size,
            "Boot image header differs from the supported legacy format")
    start = ((page_size + kernel_size + page_size - 1) // page_size) * page_size
    end = start + ramdisk_size
    require(end <= len(image), "Truncated Boot ramdisk")
    inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
    data = inflater.decompress(image[start:end], MAX_RAMDISK_BYTES + 1)
    require(inflater.eof and len(data) <= MAX_RAMDISK_BYTES and data.startswith(b"070701"),
            "Boot ramdisk is not a bounded gzip/newc archive")
    rows, offset = [], 0
    while offset + 110 <= len(data):
        header = data[offset:offset + 110]
        require(header[:6] == b"070701", "Unexpected Boot ramdisk CPIO format")
        fields = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        mode, file_size, namesize = fields[1], fields[6], fields[11]
        cursor = offset + 110
        require(namesize and cursor + namesize <= len(data), "Invalid CPIO filename")
        name_data = data[cursor:cursor + namesize]
        require(name_data.endswith(b"\x00"), "Unterminated CPIO filename")
        name = name_data[:-1].decode("utf-8", errors="strict").removeprefix("./")
        require(name and not name.startswith("/") and ".." not in PurePosixPath(name).parts,
                "Unsafe Boot ramdisk path")
        cursor = (cursor + namesize + 3) & ~3
        require(cursor + file_size <= len(data), "Truncated Boot ramdisk member")
        payload = data[cursor:cursor + file_size]
        offset = (cursor + file_size + 3) & ~3
        if name == "TRAILER!!!":
            require(file_size == 0 and not any(data[offset:]), "Invalid CPIO trailer")
            return rows
        if name in SENSITIVE_NAMES or "adbkey" in name.lower() or "adb_keys" in name.lower():
            rows.append({"path": name, "bytes": len(payload), "key_named": True})
            if payload:
                raise ValueError("ADB authorization/key material found in Boot ramdisk: " + name)
        if name.endswith(".rc") or name.endswith(".prop"):
            local_findings = []
            inspect_config_bytes(payload, "BOOT/" + name, local_findings)
            if local_findings:
                raise ValueError("ADB configuration found in Boot ramdisk: " + name)
        if PRIVATE_ARMOR.search(payload):
            raise ValueError("Private-key armor found in Boot ramdisk member: " + name)
    raise ValueError("Boot ramdisk CPIO trailer is missing")


def audit_boot_and_ota(boot_path, ota_path, system_image, tools_dir):
    boot_data = plain_file(boot_path, "Boot image").read_bytes()
    check_boot(boot_data)
    boot_hash = sha256_bytes(boot_data)
    ramdisk_keys = boot_ramdisk(boot_data)
    with zipfile.ZipFile(plain_file(ota_path, "OTA ZIP")) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "OTA ZIP contains duplicate member names")
        require("boot.img" in names, "OTA ZIP has no boot.img member")
        metadata = ota_build_metadata(archive)
        packaged_boot = archive.read("boot.img")
        require(sha256_bytes(packaged_boot) == boot_hash,
                "OTA boot.img does not match the separately audited Boot image")
        key_members = []
        for info in archive.infolist():
            basename = PurePosixPath(info.filename).name.lower()
            if basename in SENSITIVE_NAMES or "adbkey" in basename:
                key_members.append({"path": info.filename, "bytes": info.file_size})
                require(info.file_size == 0, "Nonempty ADB key-named OTA member")
        require(not key_members, "ADB key-named members are not allowed in OTA")
        system_payload = verify_system_payload(ota_path, system_image, tools_dir)
        require(system_payload.get("matches_built_system") is True,
                "OTA System transfer does not match the audited System image")
        return {"boot_sha256": boot_hash, "boot_bytes": len(boot_data),
                "boot_matches_ota": True, "ramdisk_key_paths": ramdisk_keys,
                "ota_build_metadata": metadata,
                "system_payload_matches_image": True,
                "system_payload_check": system_payload,
                "ota_sha256": sha256_file(ota_path), "ota_bytes": ota_path.stat().st_size,
                "ota_member_count": len(names), "adb_key_named_ota_members": key_members}


def input_fingerprints(target_root, system_image, boot_image, ota_zip):
    patch_index = plain_file(ROOT / "patches/index.json", "Patch index")
    return {
        "patch_index_sha256": sha256_file(patch_index),
        "target_files_tree_sha256": sha256_plain_tree(target_root),
        "system_image_sha256": sha256_file(plain_file(system_image, "System image")),
        "boot_image_sha256": sha256_file(plain_file(boot_image, "Boot image")),
        "ota_zip_sha256": sha256_file(plain_file(ota_zip, "OTA ZIP")),
    }


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True,
                        help="Android repo checkout root")
    parser.add_argument("--target-files", type=Path, required=True,
                        help="Unpacked target_files SYSTEM tree (the SYSTEM directory)")
    parser.add_argument("--system-image", type=Path, required=True,
                        help="Exact built sparse/raw System image used for OTA")
    parser.add_argument("--boot-image", type=Path, required=True,
                        help="Exact built Boot image used for OTA")
    parser.add_argument("--ota-zip", type=Path, required=True,
                        help="Full OTA ZIP produced from these target files")
    parser.add_argument("--tools-dir", type=Path, required=True,
                        help="Pinned Android host tools directory containing debugfs_static and simg2img")
    parser.add_argument("--report", type=Path, required=True,
                        help="New report path under workspace state/")
    args = parser.parse_args()
    report_path = args.report.absolute()
    state_root = ROOT / "state"
    normalized_report = report_path.resolve(strict=False)
    require(normalized_report.is_relative_to(state_root.resolve().absolute()) and
            ".." not in report_path.parts and not report_path.exists() and
            not report_path.is_symlink(), "Report must be a new file under ignored state/")
    report_path = normalized_report
    report_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    report = {"passed": False, "findings": [],
              "scope": "Read-only source/config, target-files, System image, Boot and OTA ADB/key audit; no device operations."}
    try:
        before = input_fingerprints(args.target_files, args.system_image,
                                    args.boot_image, args.ota_zip)
        report["input_fingerprints_before"] = before
        source = audit_source(args.source_root)
        report["source"] = {k: v for k, v in source.items() if k != "findings"}
        if source["findings"]:
            report["findings"] = source["findings"]
            raise ValueError("ADB source guard found a release blocker")
        target = audit_target_files(args.target_files)
        report["target_files"] = {k: v for k, v in target.items() if k != "findings"}
        if target["findings"]:
            report["findings"] = target["findings"]
            raise ValueError("ADB target-files guard found a release blocker")
        system = audit_system_image(plain_file(args.system_image, "System image"), args.tools_dir)
        report["system_image"] = {k: v for k, v in system.items() if k != "findings"}
        if system["findings"]:
            report["findings"] = system["findings"]
            raise ValueError("ADB System image guard found a release blocker")
        boot_ota = audit_boot_and_ota(args.boot_image, args.ota_zip,
                                      args.system_image, args.tools_dir)
        report["boot_and_ota"] = boot_ota
        release_properties = target["release_properties"]
        ota_metadata = boot_ota["ota_build_metadata"]
        incremental = release_properties["ro.build.version.incremental"]
        build_timestamp = release_properties["ro.build.date.utc"]
        require(ota_metadata["post-build-incremental"] == incremental and
                ota_metadata["post-timestamp"] == build_timestamp,
                "OTA build metadata does not match target-files incremental and timestamp")
        after = input_fingerprints(args.target_files, args.system_image,
                                   args.boot_image, args.ota_zip)
        report["input_fingerprints_after"] = after
        require(before == after, "Release audit inputs changed while they were being checked")
        report["release_binding"] = {
            "patch_index_sha256": before["patch_index_sha256"],
            "lineage_version": release_properties["ro.lineage.version"],
            "build_incremental": incremental,
            "build_timestamp_utc": build_timestamp,
            "ota_post_build": ota_metadata["post-build"],
            "ota_post_build_incremental": ota_metadata["post-build-incremental"],
            "ota_post_timestamp": ota_metadata["post-timestamp"],
            "ota_metadata_matches_target_files": True,
            "target_files_system_boot_ota_and_patch_index_unchanged": True,
        }
        report["passed"] = True
    except BaseException as error:
        report["error"] = str(error)
        if not report["findings"]:
            report["findings"] = [{"kind": "audit_error", "message": str(error)}]
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        print("ADB release audit report: " + str(report_path.relative_to(ROOT)), flush=True)


if __name__ == "__main__":
    main()

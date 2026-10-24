#!/usr/bin/env bash
# Source after build_env.sh and after the OTA/tools targets have completed.
set -eo pipefail

finalize_rom_release() {
    umask 077
    device=${TAB_S3_DEVICE:-gts3lwifi}
    untested=
    for candidate in $TAB_S3_UNTESTED_DEVICES; do
        if [[ $candidate == "$device" ]]; then untested=-UNTESTED; fi
    done
    package_dir=$(get_build_var PRODUCT_OUT)
    target_files="$package_dir/obj/PACKAGING/target_files_intermediates/lineage_${device}-target_files/SYSTEM"
    system_image="$package_dir/obj/PACKAGING/system_intermediates/system.img"
    boot_image="$package_dir/boot.img"
    ota_zip="$package_dir/lineage_${device}-ota.zip"
    product_prop="$target_files/product/etc/build.prop"
    system_prop="$target_files/build.prop"

    package_version=$(python3 - "$product_prop" "$system_prop" "$device" <<'PY'
import datetime
import pathlib
import re
import sys

product_prop = pathlib.Path(sys.argv[1])
system_prop = pathlib.Path(sys.argv[2])
device = sys.argv[3]

def one_property(path, name):
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"packaged property file is missing or unsafe: {path.name}")
    matches = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            matches.append(line.split("=", 1)[1])
    if len(matches) != 1 or not matches[0]:
        raise SystemExit(f"expected exactly one nonempty {name} in {path.name}")
    return matches[0]

version = one_property(product_prop, "ro.lineage.version")
build_timestamp = one_property(system_prop, "ro.build.date.utc")
match = re.fullmatch(r"24\.0-(\d{8})(?:_(\d{6}))?-UNOFFICIAL-" + re.escape(device), version)
if not match:
    raise SystemExit(f"noncanonical or unexpected Lineage version: {version!r}")
try:
    version_date = datetime.datetime.strptime(match.group(1), "%Y%m%d")
    if match.group(2):
        datetime.datetime.strptime(match.group(1) + "_" + match.group(2), "%Y%m%d_%H%M%S")
except ValueError:
    raise SystemExit("invalid calendar date or time in packaged Lineage version")
try:
    build_epoch = int(build_timestamp, 10)
    build_utc = datetime.datetime.fromtimestamp(build_epoch, datetime.timezone.utc)
except (ValueError, OverflowError, OSError):
    raise SystemExit("invalid ro.build.date.utc in packaged build.prop")
if build_utc.strftime("%Y%m%d") != version_date.strftime("%Y%m%d"):
    raise SystemExit("Lineage version date does not match packaged build timestamp")
print(version)
PY
)

    test -f "$system_image"
    test -f "$boot_image"
    test -f "$ota_zip"
    test -d "$target_files"

    # A previous package with the same build ID must not survive a failed gate.
    package_name="lineage-$package_version$untested"
    rm -f "$package_dir/$package_name.zip" \
        "$package_dir/$package_name.zip.sha256sum" \
        "$package_dir/system.img"

    report_dir=$(mktemp -d /workspace/state/release-adb-audit.XXXXXX)
    report="$report_dir/report.json"
    python3 /workspace/scripts/audit_release_adb.py \
        --source-root /workspace/android \
        --target-files "$target_files" \
        --system-image "$system_image" \
        --boot-image "$boot_image" \
        --ota-zip "$ota_zip" \
        --tools-dir /workspace/android/out/host/linux-x86/bin \
        --device "$device" \
        --report "$report"
    python3 - "$report" "$package_version" <<'PY'
import json
import pathlib
import sys

report = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
binding = report.get("release_binding", {})
if report.get("passed") is not True or binding.get("lineage_version") != sys.argv[2]:
    raise SystemExit("release ADB audit report did not pass for this packaged build")
if binding.get("target_files_system_boot_ota_and_patch_index_unchanged") is not True:
    raise SystemExit("release ADB audit did not bind stable package inputs")
PY

    cp -f "$system_image" "$package_dir/system.img"
    ln -f "$ota_zip" "$package_dir/$package_name.zip"
    sha256sum "$package_dir/$package_name.zip" \
        | sed "s|$package_dir/||" > "$package_dir/$package_name.zip.sha256sum"
    printf 'Release audit passed: %s\n' "${report#/workspace/}"
    printf 'Packaged ROM: %s\n' "$package_name.zip"
}

finalize_rom_release

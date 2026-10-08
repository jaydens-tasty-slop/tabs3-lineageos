#!/usr/bin/env python3
"""Build or validate the small local payload set used by make smoke-hardware."""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MEDIA_APK = ROOT / "artifacts/device-media-validation"
FIXTURES = ROOT / "artifacts/device-media-fixtures-v2"
VULKAN = ROOT / "artifacts/device-vulkan-validation"
MEDIA_SOURCE = ROOT / "device-validation/media/src"
VULKAN_SOURCE = ROOT / "device-validation/native/vulkan_compute.c"
VULKAN_SHADER = ROOT / "device-validation/native/vulkan_compute.comp"
VENDOR_XML = ROOT / "android/device/samsung/gts3l-common/configs/media_codecs.xml"
REQUIRED_FIXTURES = ("avc-baseline-480p", "hevc-main-480p", "aac-lc")
SDK_TOOLS = ROOT / "android/prebuilts/sdk/tools/linux/bin"
SDK_JAR = ROOT / "android/prebuilts/sdk/36/public/android.jar"


def preflight():
    missing_checkout = []
    required_checkout = {
        "media codec configuration": VENDOR_XML,
        "Vulkan probe source": VULKAN_SOURCE,
        "Vulkan shader source": VULKAN_SHADER,
        "Android 36 SDK jar": SDK_JAR,
        "Android core lambda stubs": SDK_TOOLS / "core-lambda-stubs.jar",
        "Android aapt2": SDK_TOOLS / "aapt2",
        "Android d8": SDK_TOOLS / "d8",
        "Android zipalign": SDK_TOOLS / "zipalign",
        "Android apksigner": SDK_TOOLS / "apksigner",
        "D8 jar": SDK_TOOLS.parent / "lib/d8.jar",
        "apksigner jar": SDK_TOOLS.parent / "lib/apksigner.jar",
    }
    for label, path in required_checkout.items():
        if not path.is_file():
            missing_checkout.append(label + " (" + str(path.relative_to(ROOT)) + ")")
    for name in ("aapt2", "d8", "zipalign", "apksigner"):
        path = SDK_TOOLS / name
        if path.is_file() and not os.access(path, os.X_OK):
            missing_checkout.append("executable Android " + name + " (" + str(path.relative_to(ROOT)) + ")")
    if not MEDIA_SOURCE.is_dir() or not list(MEDIA_SOURCE.rglob("*.java")):
        missing_checkout.append("media probe Java sources (no Java files found)")

    missing_host_tools = [name for name in ("java", "javac", "keytool", "ffmpeg", "ffprobe", "glslangValidator")
                          if not shutil.which(name)]
    missing_android_outputs = []
    missing_checkout_tools = []
    for name, path in vulkan_dependencies().items():
        if path.is_file() and (name != "clang" or os.access(path, os.X_OK)):
            continue
        label = name + " (" + str(path.relative_to(ROOT)) + ")"
        if name in ("clang", "header"):
            missing_checkout_tools.append(label)
        else:
            missing_android_outputs.append(label)

    bad_local_dirs = []
    for directory in (ROOT / "artifacts", ROOT / "state"):
        if directory.is_symlink() or not directory.is_dir() or not os.access(directory, os.W_OK):
            bad_local_dirs.append(str(directory.relative_to(ROOT)))

    problems = []
    if missing_checkout or missing_checkout_tools:
        missing = missing_checkout + missing_checkout_tools
        problems.append("Android checkout/SDK inputs are missing: " + ", ".join(missing)
                        + ". Run make setup first.")
    if missing_android_outputs:
        problems.append("Existing Android build outputs are missing: " + ", ".join(missing_android_outputs)
                        + ". Run make build once; smoke-payloads does not start a ROM build.")
    if missing_host_tools:
        problems.append("Payload tools are missing from PATH: " + ", ".join(missing_host_tools)
                        + ". Run make smoke-payloads through its Podman media image.")
    if bad_local_dirs:
        problems.append("Expected writable local directories are missing or unsafe: " + ", ".join(bad_local_dirs)
                        + ". Run make smoke-payloads from the workspace root.")
    key = ROOT / "state/device-smoke-media.keystore"
    if key.is_symlink():
        problems.append("Refusing linked local diagnostic keystore: " + str(key.relative_to(ROOT)))
    if problems:
        raise ValueError("Smoke payload preflight failed. " + " ".join(problems))


def digest(path):
    value = hashlib.sha256()
    with pathlib.Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Cannot validate existing smoke payload: " + str(path)) from error


def run_builder(script, *args):
    command = [sys.executable, str(ROOT / "scripts" / script), *args]
    subprocess.run(command, cwd=ROOT, check=True)


def media_apk_current():
    apk = MEDIA_APK / "tabs3-media-probe.apk"
    record_path = MEDIA_APK / "build.json"
    if MEDIA_APK.is_symlink() or not MEDIA_APK.exists():
        return False
    record = read_json(record_path)
    sources = {str(path.relative_to(ROOT)): digest(path)
               for path in sorted(MEDIA_SOURCE.rglob("*.java"))}
    tools = SDK_TOOLS
    actual_tools = {name: digest(tools / name) for name in ("aapt2", "d8", "zipalign", "apksigner")}
    jars = {name: digest(tools.parent / "lib" / name) for name in ("d8.jar", "apksigner.jar")}
    if not apk.is_file() or apk.is_symlink() or digest(apk) != record.get("apk_sha256"):
        return False
    if record.get("sources") != sources or record.get("android_jar_sha256") != digest(
            SDK_JAR):
        return False
    if record.get("tool_jars") != jars:
        return False
    builder_hash = record.get("builder_sha256")
    if builder_hash and builder_hash != digest(ROOT / "scripts/build_media_payload.py"):
        return False
    if record.get("tools", actual_tools) != actual_tools:
        return False
    permissions = MEDIA_APK / "permissions.txt"
    return permissions.is_file() and "uses-permission:" not in permissions.read_text()


def ensure_media_apk():
    if media_apk_current():
        print("Smoke media APK is current; skipped", flush=True)
    elif MEDIA_APK.exists():
        raise ValueError("Existing media payload is stale or incomplete; move artifacts/device-media-validation aside before rebuilding")
    else:
        run_builder("build_media_payload.py")
        if not media_apk_current():
            raise ValueError("Generated media APK failed its source/tool/checksum record")


def fixtures_current():
    if FIXTURES.is_symlink() or not FIXTURES.exists():
        return False
    manifest = read_json(FIXTURES / "manifest.json")
    if manifest.get("vendor_xml_sha256") != digest(VENDOR_XML):
        return False
    cases = {item.get("name"): item for item in manifest.get("cases", [])}
    expected = {
        "avc-baseline-480p": ("video", 640, 480, 30),
        "hevc-main-480p": ("video", 640, 480, 30),
        "aac-lc": ("audio", None, None, None),
    }
    for name, (kind, width, height, fps) in expected.items():
        case = cases.get(name)
        if not case or case.get("kind") != kind:
            return False
        if kind == "video" and (case.get("width"), case.get("height"), case.get("fps"), case.get("frames")) != (width, height, fps, 30):
            return False
        if kind == "audio" and case.get("duration_seconds") != 2:
            return False
        file = FIXTURES / str(case.get("file", ""))
        if file.parent != FIXTURES or not file.is_file() or file.is_symlink() or digest(file) != case.get("sha256"):
            return False
    return True


def ensure_fixtures():
    if fixtures_current():
        print("Required AVC/HEVC/AAC fixtures are current; skipped", flush=True)
    elif FIXTURES.exists():
        raise ValueError("Existing media fixtures are stale or incomplete; move artifacts/device-media-fixtures-v2 aside before rebuilding")
    else:
        run_builder("generate_media_fixtures.py", *(arg for case in REQUIRED_FIXTURES for arg in ("--case", case)))
        if not fixtures_current():
            raise ValueError("Generated AVC/HEVC/AAC fixtures failed their manifest checks")


def vulkan_dependencies():
    bionic = ROOT / "android/out/soong/.intermediates/bionic/libc"
    return {
        "clang": ROOT / "android/prebuilts/clang/host/linux-x86/clang-r563880c/bin/clang",
        "vulkan": ROOT / "android/out/target/product/gts3lwifi/system/lib64/libvulkan.so",
        "libc": bionic / "libc/android_arm64_armv8-a_shared/libc.so",
        "crtbegin": bionic / "crtbegin_dynamic/android_arm64_armv8-a/crtbegin_dynamic.o",
        "crtend": bionic / "crtend_android/android_arm64_armv8-a/crtend_android.o",
        "header": ROOT / "android/external/vulkan-headers/include/vulkan/vulkan_core.h",
    }


def vulkan_current():
    if VULKAN.is_symlink() or not VULKAN.exists():
        return False
    record = read_json(VULKAN / "build.json")
    binary = VULKAN / "vulkan-compute"
    if not binary.is_file() or binary.is_symlink() or digest(binary) != record.get("sha256"):
        return False
    sources = {str(path.relative_to(ROOT)): digest(path) for path in (VULKAN_SOURCE, VULKAN_SHADER)}
    if record.get("sources") != sources:
        return False
    generator_hash = record.get("generator_sha256")
    if generator_hash and generator_hash != digest(ROOT / "scripts/build_vulkan_validation.py"):
        return False
    dependency_keys = {"clang": "clang_sha256", "vulkan": "vulkan_library_sha256",
                       "libc": "libc_sha256", "header": "header_sha256"}
    for name, path in vulkan_dependencies().items():
        if not path.is_file():
            return False
        key = dependency_keys.get(name)
        if key and record.get(key) != digest(path):
            return False
    spirv = VULKAN / "shader.spv"
    if not spirv.is_file() or digest(spirv) != record.get("spirv_sha256"):
        return False
    glslang = shutil.which("glslangValidator")
    if record.get("glslang_sha256") and (not glslang or digest(glslang) != record["glslang_sha256"]):
        return False
    return True


def ensure_vulkan():
    if vulkan_current():
        print("Vulkan smoke binary is current; skipped", flush=True)
    elif VULKAN.exists():
        raise ValueError("Existing Vulkan payload is stale or incomplete; move artifacts/device-vulkan-validation aside before rebuilding")
    else:
        missing = [str(path) for path in vulkan_dependencies().values() if not path.is_file()]
        if missing:
            raise ValueError("Vulkan smoke payload needs existing Android build outputs; run make build first: " + ", ".join(missing))
        run_builder("build_vulkan_validation.py")
        if not vulkan_current():
            raise ValueError("Generated Vulkan binary failed its source/tool/checksum record")


def main():
    os.umask(0o077)
    preflight()
    ensure_media_apk()
    ensure_fixtures()
    ensure_vulkan()
    print("Smoke payloads are ready under ignored artifacts/ and state/", flush=True)


if __name__ == "__main__":
    main()

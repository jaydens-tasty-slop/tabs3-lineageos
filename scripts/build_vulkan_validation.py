#!/usr/bin/env python3
"""Build a Vulkan compute diagnostic from cloned Android tools in media Podman."""
import hashlib
import json
import pathlib
import shutil
import struct
import subprocess

ROOT=pathlib.Path(__file__).resolve().parent.parent


def digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def main():
    output=ROOT / "artifacts/device-vulkan-validation";output.mkdir(exist_ok=True)
    source=ROOT / "device-validation/native/vulkan_compute.c"
    shader=source.with_suffix(".comp");spirv=output / "shader.spv"
    glslang=shutil.which("glslangValidator")
    if not glslang:
        raise RuntimeError("Build this payload in the Tab S3 smoke Podman image (glslangValidator is required)")
    subprocess.run([glslang,"-V","--target-env","vulkan1.0","-o",str(spirv),str(shader)],check=True)
    code=spirv.read_bytes()
    if len(code)%4 or code[:4]!=b"\x03\x02\x23\x07":raise ValueError("Invalid SPIR-V")
    header=output / "vulkan_compute_spirv.h"
    header.write_text("static const uint32_t probe_spirv[]={"+",".join(hex(word[0])+"u" for word in struct.iter_unpack("<I",code))+"};\n")
    clang=ROOT / "android/prebuilts/clang/host/linux-x86/clang-r563880c/bin/clang"
    bionic=ROOT / "android/out/soong/.intermediates/bionic/libc"
    begin=bionic / "crtbegin_dynamic/android_arm64_armv8-a/crtbegin_dynamic.o"
    end=bionic / "crtend_android/android_arm64_armv8-a/crtend_android.o"
    libc=bionic / "libc/android_arm64_armv8-a_shared/libc.so"
    vulkan=ROOT / "android/out/target/product/gts3lwifi/system/lib64/libvulkan.so"
    headers=ROOT / "android/external/vulkan-headers/include"
    binary=output / "vulkan-compute"
    command=[str(clang),"--target=aarch64-linux-android36","-O2","-Wall","-Wextra","-Werror",
             "-ffreestanding","-fPIE","-pie","-nostdlib","-Wl,--dynamic-linker,/system/bin/linker64",
             "-Wl,-z,relro,-z,now","-Wl,--no-undefined","-I"+str(headers),"-I"+str(output),
             str(begin),str(source),str(vulkan),str(libc),str(end),"-o",str(binary)]
    subprocess.run(command,check=True)
    data=binary.read_bytes()
    if data[:6]!=b"\x7fELF\x02\x01" or int.from_bytes(data[18:20],"little")!=183:
        raise ValueError("Expected AArch64 ELF")
    report={"sha256":digest(binary),"sources":{str(p.relative_to(ROOT)):digest(p) for p in (source,shader)},
        "spirv_sha256":digest(spirv),"command":command,"clang_sha256":digest(clang),
        "vulkan_library_sha256":digest(vulkan),"libc_sha256":digest(libc),
        "header_sha256":digest(headers / "vulkan/vulkan_core.h"),"glslang_sha256":digest(glslang),
        "generator_sha256":digest(pathlib.Path(__file__)),
        "glslang_version":subprocess.check_output([glslang,"--version"],text=True),
        "scope":"Vulkan 1.0 Qualcomm compute, 64 rounds / 8192 exact values. Drops to UID/GID 2000 and checks zero capabilities before Vulkan calls. No personal storage or Activity."}
    (output / "build.json").write_text(json.dumps(report,indent=2)+"\n")
    print("Built Vulkan compute diagnostic: "+str(binary),flush=True)


if __name__=="__main__":main()

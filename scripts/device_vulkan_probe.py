#!/usr/bin/env python3
"""Run generated Vulkan compute as shell UID and preserve exact GPU results."""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import uuid
from adb_device import AdbDevice,private_directory
from device_smoke_common import file_hash,require

ROOT=pathlib.Path(__file__).resolve().parent.parent


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--serial",required=True)
    args=parser.parse_args();device=AdbDevice(args.serial)
    require(not device.recovery and device.props.get("ro.build.version.sdk")=="37"
            and device.props.get("sys.boot_completed")=="1","Booted Android 17 required")
    require(device.shell("id -u",check=True).stdout.strip()=="2000","Use ordinary Android shell UID 2000")
    artifact=ROOT / "artifacts/device-vulkan-validation";binary=artifact / "vulkan-compute"
    build=json.loads((artifact / "build.json").read_text())
    require(binary.is_file() and not binary.is_symlink() and file_hash(binary)==build["sha256"],"Diagnostic binary checksum changed")
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ");token=uuid.uuid4().hex[:8]
    output=private_directory(ROOT / "diagnostics" / (stamp+"-vulkan-"+token));remote="/data/local/tmp/tabs3-vulkan-"+token
    report={"passed":False,"serial":args.serial,"binary_sha256":build["sha256"],
        "scope":build["scope"],"limits":"Compute correctness only. Does not establish Vulkan presentation, games, HDR or thermal endurance."}
    (output / "build.json").write_text(json.dumps(build,indent=2)+"\n");staged=False
    try:
        device.shell("test ! -e "+remote+" && mkdir -m 0755 "+remote,check=True);staged=True
        subprocess.run(device.command+["push",str(binary),remote+"/compute"],check=True,capture_output=True,timeout=30)
        require(device.shell("sha256sum "+remote+"/compute",check=True).stdout.split()[0]==build["sha256"],"USB checksum failed")
        device.shell("chmod 0755 "+remote+"/compute",check=True)
        report["before"]=device.shell("pidof system_server; cat /proc/sys/kernel/random/boot_id; am get-started-user-state 0",check=True).stdout
        result=device.shell(remote+"/compute",timeout=70)
        (output / "output.txt").write_text(result.stdout+result.stderr)
        lines=[line.removeprefix("TAB_S3_NATIVE_REPORT ") for line in result.stdout.splitlines() if line.startswith("TAB_S3_NATIVE_REPORT ")]
        require(len(lines)==1,"Native runner did not return one complete JSON report")
        native=json.loads(lines[0]);report["result"]=native
        require(native["uid"]==native["gid"]==2000 and native["process_capabilities_zero"] is True,"Unexpected diagnostic credentials")
        report["after"]=device.shell("pidof system_server; cat /proc/sys/kernel/random/boot_id; am get-started-user-state 0",check=True).stdout
        report["framework_unchanged"]=report["before"]==report["after"]
        report["passed"]=result.returncode==0 and native["passed"] is True and native["verified_values"]==8192
        report["passed"] &= native["rounds"]==64 and native["vendor_id"]==0x5143 and report["framework_unchanged"]
    except BaseException as error:report["error"]=str(error);raise
    finally:
        cleanup={"passed":True,"steps":{}}
        if staged:
            try:
                device.shell("rm -f "+remote+"/compute && rmdir "+remote,check=True)
                cleanup["steps"]["staging_directory"]=True
            except BaseException as error:
                cleanup["passed"]=False
                cleanup["steps"]["staging_directory"]=False
                report["error_cleanup"]=str(error)
        report["cleanup"]=cleanup
        if not cleanup["passed"]:report["passed"]=False
        (output / "report.json").write_text(json.dumps(report,indent=2)+"\n")
        print("Vulkan evidence: "+str(output / "report.json")+"; passed="+str(report["passed"]),flush=True)
    if not report["passed"]:raise SystemExit(1)


if __name__=="__main__":main()

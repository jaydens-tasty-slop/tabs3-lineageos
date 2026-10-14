#!/usr/bin/env python3
"""Run bounded camera/sensor/microphone probes; export counters, never media content."""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import shlex
import subprocess
import time
import uuid
from adb_device import AdbDevice, private_directory
from device_smoke_common import file_hash, require

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = "org.tabs3.validation.io"
ACTIVITY = PACKAGE + "/" + PACKAGE + ".MainActivity"


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial",required=True)
    parser.add_argument("--suite",choices=("audio","camera","sensors","all"),default="all")
    parser.add_argument("--keep-app",action="store_true")
    args=parser.parse_args()
    device=AdbDevice(args.serial)
    require(not device.recovery and device.props.get("sys.boot_completed")=="1"
            and device.props.get("ro.build.version.sdk")=="37","Requires the booted Android 17 tablet")
    require(device.shell("am get-started-user-state 0",check=True).stdout.strip()=="RUNNING_UNLOCKED",
            "Unlock Android user 0 with its normal PIN/pattern after reboot before running app probes")
    policy=device.shell("dumpsys window policy",check=True).stdout
    require("mIsShowing=false" in policy or re.search(r"^\s*showing=false\s*$",policy,re.M),
            "Unlock the current screen normally before camera/microphone foreground tests")
    payload=ROOT / "artifacts/device-io-validation";apk=payload / "tabs3-io-probe.apk"
    build=json.loads((payload / "build.json").read_text())
    require(file_hash(apk)==build["apk_sha256"],"I/O APK checksum differs from its build")
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory=private_directory(ROOT / "diagnostics" / (stamp+"-io-"+args.suite+"-"+uuid.uuid4().hex[:8]))
    report={"serial":args.serial,"suite":args.suite,"apk_sha256":build["apk_sha256"],"results":[],"errors":[],
            "limits":["No photographs or microphone PCM are saved or exported",
                      "Sensor events on a stationary tablet do not establish calibration or physical motion response"]}
    installed_here=False

    def adb(arguments,timeout=60,check=True):
        return subprocess.run(device.command+arguments,check=check,capture_output=True,text=True,timeout=timeout)

    try:
        lookup=device.shell("pm path "+PACKAGE)
        if lookup.stdout.strip():
            paths=[line.removeprefix("package:") for line in lookup.stdout.splitlines()]
            require(len(paths)==1 and paths[0].startswith("/data/app/")
                    and device.shell("sha256sum "+shlex.quote(paths[0]),check=True).stdout.split()[0]==build["apk_sha256"],
                    "Existing I/O diagnostic has different bytes; explicitly remove it before replacing")
        else:
            require(lookup.returncode in (0,1),"Package lookup failed")
            adb(["install","--no-streaming",str(apk)],timeout=120);installed_here=True
        suites=("audio","sensors","camera") if args.suite=="all" else (args.suite,)
        if "audio" in suites:device.shell("pm grant "+PACKAGE+" android.permission.RECORD_AUDIO",check=True)
        if "camera" in suites:device.shell("pm grant "+PACKAGE+" android.permission.CAMERA",check=True)
        report["framework_before"]=device.shell("pidof system_server; cat /proc/sys/kernel/random/boot_id",check=True).stdout
        services="pidof android.hardware.audio.service.gts3l; pidof android.hardware.camera.provider@2.4-service"
        report["hardware_services_before"]=device.shell(services,check=True).stdout
        for suite in suites:
            filename=suite+"-"+uuid.uuid4().hex[:8]+".json"
            device.shell("am force-stop "+PACKAGE,check=True)
            launch=device.shell("am start -W -n "+ACTIVITY+" --es command "+suite+" --es output "+filename,timeout=30)
            (directory / (suite+"-launch.txt")).write_text(launch.stdout+launch.stderr)
            require(launch.returncode==0 and "Error:" not in launch.stdout,"I/O activity did not start")
            deadline=time.monotonic()+(240 if suite=="camera" else 60)
            item=None
            map_files=[]
            while time.monotonic()<deadline:
                if suite=="camera":
                    pids=device.shell("pidof android.hardware.camera.provider@2.4-service").stdout.split()
                    for pid in pids:
                        require(pid.isdecimal(),"Unexpected camera provider PID")
                        maps=device.shell("cat /proc/"+pid+"/maps").stdout
                        if maps:
                            name="camera-maps-"+pid+"-"+hashlib.sha256(maps.encode()).hexdigest()[:12]+".txt"
                            if name not in map_files and len(map_files)<128:
                                (directory / name).write_text(maps);map_files.append(name)
                raw=adb(["exec-out","run-as",PACKAGE,"cat","files/"+filename],timeout=10,check=False)
                if raw.returncode==0 and raw.stdout.lstrip().startswith("{"):
                    item=json.loads(raw.stdout);break
                time.sleep(.1 if suite=="camera" else 1)
            if item is None:item={"command":suite,"passed":False,"error":"App report timeout"}
            if suite=="camera":item["provider_map_observations"]=map_files
            (directory / (suite+".json")).write_text(json.dumps(item,indent=2)+"\n")
            report["results"].append(item)
            device.shell("run-as "+PACKAGE+" rm -f files/"+filename)
            (directory / "report.json").write_text(json.dumps(report,indent=2)+"\n")
            print(suite+": "+str(item.get("passed")),flush=True)
        # Provider destructors can crash just after CameraDevice.close returns.
        time.sleep(5)
        report["hardware_services_after"]=device.shell(services).stdout
        report["hardware_services_unchanged"]=report["hardware_services_before"]==report["hardware_services_after"]
        report["framework_after"]=device.shell("pidof system_server; cat /proc/sys/kernel/random/boot_id").stdout
        report["framework_unchanged"]=report["framework_after"]==report["framework_before"]
        report["passed"]=all(item.get("passed") is True for item in report["results"]) and report["framework_unchanged"] and report["hardware_services_unchanged"]
    except BaseException as error:report["passed"]=False;report["errors"].append(str(error));raise
    finally:
        try:
            device.shell("am force-stop "+PACKAGE)
            # Revoke only this diagnostic's permissions when it is retained.
            if args.keep_app:
                for permission in ("CAMERA","RECORD_AUDIO"):device.shell("pm revoke "+PACKAGE+" android.permission."+permission)
            elif installed_here:report["probe_removed"]=adb(["uninstall",PACKAGE],check=False).returncode==0
            log=adb(["logcat","-b","all","-d","-v","threadtime","-t","30000"],check=False)
            (directory / "logcat.txt").write_text(log.stdout+log.stderr)
        except (OSError,subprocess.SubprocessError) as error:report["errors"].append("Cleanup/capture: "+str(error))
        (directory / "report.json").write_text(json.dumps(report,indent=2)+"\n")
        print("I/O evidence: "+str(directory / "report.json"),flush=True)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":main()

#!/usr/bin/env python3
"""Run ordinary non-camera probes after normal unlock, restoring USB stay-awake."""
import argparse
import datetime
import json
import pathlib
import re
import subprocess
import sys
import time
import uuid

from adb_device import AdbDevice, private_directory
from device_smoke_common import require

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial')
    parser.add_argument('--wait-unlock-seconds', type=int, default=180)
    parser.add_argument('--suite', action='append', choices=(
        'media', 'gpu', 'audio-route', 'webview', 'vulkan'))
    args = parser.parse_args()
    require(30 <= args.wait_unlock_seconds <= 600, 'Use a bounded 30–600-second unlock wait')
    suites = args.suite or ['media', 'gpu', 'audio-route', 'webview', 'vulkan']
    require(len(suites) == len(set(suites)), 'Do not repeat suites in one run')
    device = AdbDevice(args.serial)
    args.serial = device.serial
    require(not device.recovery and device.props.get('ro.build.version.sdk') == '36'
            and device.props.get('sys.boot_completed') == '1', 'Booted Android 16 required')
    require(device.shell('id -u', check=True).stdout.strip() == '2000',
            'Use ordinary Android shell UID 2000; root ADB is outside this smoke scope')
    setup_complete = device.shell(
        'settings --user 0 get secure user_setup_complete', check=True).stdout.strip()
    provisioned = device.shell(
        'settings get global device_provisioned', check=True).stdout.strip()
    require(setup_complete == '1' and provisioned == '1',
            'Complete Android first-run setup, then unlock normally before foreground probes')
    battery = device.shell('dumpsys battery', check=True).stdout
    require(re.search(r'^\s*USB powered: true\s*$', battery, re.M), 'Requires USB power')
    setting = device.shell('settings get global stay_on_while_plugged_in', check=True).stdout.strip()
    require(setting == 'null' or re.fullmatch(r'\d+', setting), 'Unexpected stay-awake setting')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = private_directory(ROOT / 'diagnostics' / (stamp + '-foreground-' + uuid.uuid4().hex[:8]))
    report = {'serial': args.serial, 'passed': False, 'suites': suites, 'results': [],
              'stay_awake_original': setting, 'normal_unlock_required': True,
              'limits': ['Camera tests are not included', 'No lock credentials are accessed or modified']}
    changed = False
    try:
        changed = True  # Restore even if the command partially succeeds.
        device.shell('svc power stayon usb', check=True)
        require(device.shell('settings get global stay_on_while_plugged_in', check=True).stdout.strip() == '2',
                'USB stay-awake was not applied')
        print('Waiting for normal screen unlock; temporary USB stay-awake is active', flush=True)
        deadline = time.monotonic() + args.wait_unlock_seconds
        while True:
            state = device.shell('am get-started-user-state 0', check=True).stdout.strip()
            policy = device.shell('dumpsys window policy', check=True).stdout
            if state == 'RUNNING_UNLOCKED' and 'mIsShowing=false' in policy:
                break
            require(time.monotonic() < deadline, 'Normal unlock was not observed before the deadline')
            time.sleep(0.5)
        report['unlock_observed'] = True
        report['framework_before'] = device.shell('pidof system_server; cat /proc/sys/kernel/random/boot_id', check=True).stdout
        for suite in suites:
            policy = device.shell('dumpsys window policy', check=True).stdout
            require('mIsShowing=false' in policy, 'The screen locked before the next foreground probe')
            if suite == 'vulkan':
                helper = 'device_vulkan_probe.py'
                command = [sys.executable, str(ROOT / 'scripts' / helper), '--serial', args.serial]
                pattern = '*-vulkan-*'
            else:
                helper = 'device_media_probe.py'
                command = [sys.executable, str(ROOT / 'scripts' / helper), '--serial', args.serial]
                if suite == 'media':
                    command += ['--suite', 'decode']
                    for case in ('avc-baseline-480p', 'hevc-main-480p', 'aac-lc'):
                        command += ['--case', case]
                    pattern = '*-media-decode-*'
                else:
                    child_suite = 'audio-route' if suite == 'audio-route' else suite
                    command += ['--suite', child_suite]
                    pattern = '*-media-' + child_suite + '-*'
            before = set((ROOT / 'diagnostics').glob(pattern))
            log = output / (suite + '-harness.txt')
            with log.open('w') as stream:
                completed = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            after = set((ROOT / 'diagnostics').glob(pattern))
            created = sorted(after - before)
            item = {'suite': suite, 'returncode': completed.returncode,
                    'reports': [str(p.relative_to(ROOT) / 'report.json') for p in created]}
            require(len(created) == 1 and (created[0] / 'report.json').is_file(), 'Missing unique child report')
            child = json.loads((created[0] / 'report.json').read_text())
            item['passed'] = completed.returncode == 0 and child.get('passed') is True
            report['results'].append(item)
            (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
            print(suite + ': passed=' + str(item['passed']), flush=True)
        report['framework_after'] = device.shell('pidof system_server; cat /proc/sys/kernel/random/boot_id', check=True).stdout
        report['framework_unchanged'] = report['framework_before'] == report['framework_after']
        report['passed'] = all(item['passed'] for item in report['results']) and report['framework_unchanged']
    except Exception as error:
        report['error'] = str(error)
    finally:
        if changed:
            command = ('settings delete global stay_on_while_plugged_in' if setting == 'null'
                       else 'settings put global stay_on_while_plugged_in ' + setting)
            try:
                restored = device.shell(command, check=True)
                report['stay_awake_restored'] = restored.returncode == 0 and device.shell(
                    'settings get global stay_on_while_plugged_in', check=True).stdout.strip() == setting
            except (OSError, subprocess.SubprocessError) as error:
                report['stay_awake_restored'] = False
                report['restore_error'] = str(error)
            if not report['stay_awake_restored']:
                report['passed'] = False
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('Foreground evidence: ' + str(output / 'report.json') + '; passed=' + str(report['passed']), flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()

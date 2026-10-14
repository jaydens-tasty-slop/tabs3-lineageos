#!/usr/bin/env python3
"""Archive a bounded warm-app transition workload and ordinary Android frame stats."""
import argparse
import csv
import datetime
import json
import math
import os
import pathlib
import re
import shlex
import threading
import time
import uuid

from adb_device import AdbDevice, private_directory
from device_smoke_common import file_hash, require
from device_fdroid_validation import thermal

ROOT = pathlib.Path(__file__).resolve().parent.parent
APPS = (('com.android.settings', '.Settings'),
        ('com.kgurgul.cpuinfo', '.HostActivity'),
        ('org.fdroid.fdroid', '.views.main.MainActivity'))
SAMPLE = r'''
for f in /proc/uptime /proc/loadavg /proc/meminfo /proc/vmstat /proc/stat \
 /proc/swaps /sys/devices/system/cpu/online \
 /sys/devices/system/cpu/cpu[02]/cpufreq/scaling_cur_freq \
 /sys/devices/system/cpu/cpu[02]/cpufreq/scaling_min_freq \
 /sys/devices/system/cpu/cpu[02]/cpufreq/scaling_max_freq \
 /sys/devices/system/cpu/cpu[02]/cpufreq/scaling_governor \
 /sys/class/kgsl/kgsl-3d0/gpuclk /sys/class/kgsl/kgsl-3d0/gpubusy \
 /sys/class/kgsl/kgsl-3d0/min_pwrlevel /sys/class/kgsl/kgsl-3d0/max_pwrlevel \
 /sys/class/kgsl/kgsl-3d0/devfreq/cur_freq /sys/class/kgsl/kgsl-3d0/devfreq/min_freq \
 /sys/class/kgsl/kgsl-3d0/devfreq/max_freq \
 /sys/module/cpu_boost/parameters/input_boost_freq \
 /sys/module/cpu_boost/parameters/input_boost_ms \
 /sys/module/cpu_boost/parameters/dynamic_stune_boost \
 /dev/stune/top-app/schedtune.boost /dev/stune/top-app/schedtune.prefer_idle \
 /dev/cpuset/top-app/cpus /dev/cpuset/foreground/cpus \
 /sys/block/zram0/mm_stat /sys/block/zram0/stat;
do if [ -r "$f" ]; then printf '\n@@FILE %s\n' "$f"; cat "$f"; fi; done
'''


def identity(device):
    return {'boot_id': device.shell('cat /proc/sys/kernel/random/boot_id', check=True).stdout.strip(),
            'system_server': device.shell('pidof system_server', check=True).stdout.strip(),
            'network_stack': device.shell('pidof com.android.networkstack.process', check=True).stdout.strip(),
            'surface_flinger': device.shell('pidof surfaceflinger', check=True).stdout.strip()}


def keyguard_dismissed(policy):
    return ('mIsShowing=false' in policy or
            re.search(r'^\s*showing=false\s*$', policy, re.M) is not None)


def sections(raw):
    pieces = re.split(r'\n@@FILE ([^\n]+)\n', raw)
    return {pieces[i]: pieces[i + 1].strip() for i in range(1, len(pieces) - 1, 2)}


def snapshot(device, directory, label):
    commands = {
        'system-sample': SAMPLE,
        'activity-processes': 'dumpsys activity processes',
        'surfaceflinger': 'dumpsys SurfaceFlinger',
        'power-services': 'service list',
        'hal-services': 'lshal',
        'processes': 'ps -A -o PID,PPID,NAME',
        'settings': 'settings get global window_animation_scale; settings get global transition_animation_scale; settings get global animator_duration_scale; settings get global low_power; settings get global stay_on_while_plugged_in',
        'cgroups': 'cat /proc/cgroups; cat /proc/mounts; cat /system/etc/cgroups.json; cat /system/etc/task_profiles.json; cat /vendor/etc/task_profiles.json',
        'power-properties': 'getprop | toybox grep -E "perf|power|hwui|renderer|dalvik.vm"',
    }
    for name, command in commands.items():
        result = device.shell(command, timeout=40)
        (directory / (label + '-' + name + '.txt')).write_text(result.stdout + '\nSTDERR:\n' + result.stderr)
        require('DEAD_OBJECT' not in result.stderr, 'Android service died during snapshot')
    return {'identity': identity(device), 'thermal': thermal(device),
            'system_sample': sections(device.shell(SAMPLE, check=True).stdout)}


def percentile(values, quantile):
    values = sorted(values)
    return round(values[max(0, math.ceil(quantile * len(values)) - 1)], 3) if values else None


def launch_activity(launch):
    matches = re.findall(r'^Activity:\s*([\w.]+/[\w.$]+)\s*$', launch, re.M)
    require(len(matches) == 1, 'Launch did not report a unique activity')
    return matches[0]


def resumed_activity(device, package):
    raw = device.shell('dumpsys activity activities', check=True).stdout
    matches = re.findall(r'topResumedActivity=ActivityRecord\{[^\n}]*?\bu0\s+([\w.]+/[\w.$]+)', raw)
    require(len(matches) == 1 and matches[0].split('/')[0] == package,
            'Expected workload app is not the top resumed activity: ' + package)
    return matches[0]


def frame_stats(raw):
    summaries = []
    process_part = raw.split('Profile data in ms:', 1)[0]
    for expression, key in ((r'Total frames rendered: (\d+)', 'total_frames'),
                            (r'Janky frames: (\d+)', 'janky_frames'),
                            (r'Janky frames \(legacy\): (\d+)', 'legacy_janky_frames'),
                            (r'Number Slow UI thread: (\d+)', 'slow_ui_thread'),
                            (r'Number Slow issue draw commands: (\d+)', 'slow_draw_commands')):
        match = re.search(expression, process_part)
        if match:
            summaries.append((key, int(match.group(1))))
    rows = []; headers = None
    for line in raw.splitlines():
        if line.startswith('Flags,'):
            headers = next(csv.reader([line]))
        elif headers and re.match(r'^\d+,\d+,', line):
            values = next(csv.reader([line]))
            if len(values) == len(headers):
                row = {key: int(value) for key, value in zip(headers, values) if key and value}
                rows.append(row)
        elif line == '---PROFILEDATA---':
            headers = None
    # Per-window ring buffers can overlap; count each vsync/complete pair once.
    unique = {(r.get('FrameTimelineVsyncId'), r.get('FrameCompleted')): r for r in rows}
    valid = [r for r in unique.values() if r.get('FrameCompleted', 0) > r.get('IntendedVsync', 0) > 0
             and r['FrameCompleted'] < 2**63 - 1]
    durations = [(r['FrameCompleted'] - r['IntendedVsync']) / 1e6 for r in valid]
    gpu_rows = [r for r in valid
                if 0 < r.get('IssueDrawCommandsStart', 0) <= r.get('GpuCompleted', 0) < 2**63 - 1]
    gpu = [(r['GpuCompleted'] - r['IssueDrawCommandsStart']) / 1e6 for r in gpu_rows]
    deadline_rows = [r for r in gpu_rows
                     if r['IntendedVsync'] < r.get('FrameDeadline', 0) < 2**63 - 1]
    missed = sum(r['GpuCompleted'] > r['FrameDeadline'] for r in deadline_rows) if deadline_rows else None
    unflagged = [(r['FrameCompleted'] - r['IntendedVsync']) / 1e6 for r in valid if r.get('Flags', 0) == 0]
    return {**dict(summaries), 'ring_frames': len(valid),
            'ring_flagged_frames': sum(r.get('Flags', 0) != 0 for r in valid),
            'ring_unflagged_frames': len(unflagged),
            'ring_gpu_timestamp_samples': len(gpu_rows),
            'ring_gpu_timestamp_unavailable_frames': len(valid) - len(gpu_rows),
            'ring_gpu_deadline_samples': len(deadline_rows),
            'ring_gpu_deadline_misses': missed,
            'ring_duration_ms': {'p50': percentile(durations, .5), 'p90': percentile(durations, .9),
                                 'p95': percentile(durations, .95), 'p99': percentile(durations, .99),
                                 'max': max(durations, default=None)},
            'ring_unflagged_duration_ms': {'p50': percentile(unflagged, .5), 'p95': percentile(unflagged, .95),
                                          'p99': percentile(unflagged, .99), 'max': max(unflagged, default=None)},
            'ring_issue_to_gpu_ms': {'p50': percentile(gpu, .5), 'p95': percentile(gpu, .95)},
            'ring_frames_over_50ms': sum(v > 50 for v in durations),
            'ring_frames_over_100ms': sum(v > 100 for v in durations),
            'interpretation': 'Android process histogram is authoritative for its own jank definition; ring buffers are recent frames only. Flagged and unflagged durations are separate. Zero, missing and sentinel GPU/deadline timestamps are unavailable, not stalled frames.'}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--phase', choices=('snapshot', 'switch'), default='snapshot')
    parser.add_argument('--rounds', type=int, default=6)
    parser.add_argument('--wait-unlock-seconds', type=int, default=300)
    parser.add_argument('--sampling', choices=('system', 'none'), default='system',
                        help='Repeat the same workload without frequency/VM polling to check observer overhead')
    args = parser.parse_args()
    require(2 <= args.rounds <= 8 and 30 <= args.wait_unlock_seconds <= 600, 'Use bounded rounds and unlock wait')
    device = AdbDevice(args.serial)
    require(not device.recovery and device.props.get('ro.build.version.sdk') == '37'
            and device.props.get('sys.boot_completed') == '1', 'Booted Android 17 required')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = private_directory(ROOT / 'diagnostics' / (stamp + '-ui-performance-' + uuid.uuid4().hex[:8]))
    (directory / 'harness.py').write_bytes(pathlib.Path(__file__).read_bytes())
    report = {'created_utc': stamp, 'phase': args.phase, 'serial': args.serial,
              'harness_sha256': file_hash(directory / 'harness.py'), 'completed': False,
              'rom_fingerprint': device.props.get('ro.build.fingerprint'),
              'sampling_mode': args.sampling,
              'scope': 'Bounded warm app/home transitions with verified foreground app; sampled frequencies are not a continuous scheduling trace. ADB task launches do not generate physical touchscreen input boost.'}
    before = identity(device)
    report['initial_identity'] = before
    setting = device.shell('settings get global stay_on_while_plugged_in', check=True).stdout.strip()
    require(setting == 'null' or re.fullmatch(r'\d+', setting), 'Unexpected stay-awake setting')
    samples = []; sampling_stop = threading.Event(); thread = None
    try:
        report['before'] = snapshot(device, directory, 'before')
        if args.phase == 'switch':
            require('USB powered: true' in device.shell('dumpsys battery', check=True).stdout, 'USB power required')
            device.shell('settings put global stay_on_while_plugged_in 2', check=True)
            print('Waiting for normal unlock; warm transitions will use Settings, CPU Info and F-Droid: ' + str(directory), flush=True)
            deadline = time.monotonic() + args.wait_unlock_seconds
            while time.monotonic() < deadline:
                state = device.shell('am get-started-user-state 0', check=True).stdout.strip()
                if state == 'RUNNING_UNLOCKED' and keyguard_dismissed(device.shell('dumpsys window policy', check=True).stdout):
                    break
                time.sleep(2)
            else:
                raise ValueError('Normal unlock was not observed')
            report['warmup_launches'] = []
            for package, activity in APPS:
                require(device.shell('pm path ' + package, check=True).stdout.strip(), 'Workload app missing')
                launch = device.shell('am start -W -n ' + package + '/' + activity, check=True)
                require('Error:' not in launch.stdout, 'Warm launch failed')
                reported_activity = launch_activity(launch.stdout)
                time.sleep(2)
                report['warmup_launches'].append({'package': package, 'launch': launch.stdout,
                                                'reported_activity': reported_activity,
                                                'launch_timing_valid_for_expected_app': reported_activity.split('/')[0] == package,
                                                'top_resumed_activity': resumed_activity(device, package)})
            home = device.shell('cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME', check=True).stdout
            home_matches = re.findall(r'^([\w.]+)/[\w.$]+$', home, re.M)
            require(len(home_matches) == 1, 'Unique normal launcher not resolved')
            packages = tuple(p for p, a in APPS) + (home_matches[0], 'com.android.systemui')
            report['packages'] = packages
            for package in packages:
                raw = device.shell('dumpsys gfxinfo ' + package + ' framestats', check=True).stdout
                (directory / ('pre-reset-' + package + '-gfxinfo.txt')).write_text(raw)
                device.shell('dumpsys gfxinfo ' + package + ' reset', check=True)
            report['start_processes'] = {p: device.shell('pidof ' + p).stdout.strip() for p in packages}
            start = time.monotonic()

            def sample_loop():
                while not sampling_stop.is_set():
                    try:
                        raw = device.shell(SAMPLE, timeout=10, check=True).stdout
                        samples.append({'elapsed_seconds': round(time.monotonic()-start, 3), 'files': sections(raw)})
                    except Exception as exc:
                        samples.append({'elapsed_seconds': round(time.monotonic()-start, 3), 'error': str(exc)})
                    sampling_stop.wait(.75)

            if args.sampling == 'system':
                thread = threading.Thread(target=sample_loop, daemon=True); thread.start()
            transitions = []; thermal_samples = []
            for round_number in range(args.rounds):
                thermal_samples.append(thermal(device))
                require(identity(device) == before, 'Core process identity changed')
                for package, activity in APPS:
                    require(keyguard_dismissed(device.shell('dumpsys window policy', check=True).stdout),
                            'The screen locked before the next transition')
                    device.shell('input keyevent KEYCODE_HOME', check=True)
                    time.sleep(.9)
                    launch = device.shell('am start -W -n ' + package + '/' + activity, timeout=20, check=True).stdout
                    require('Error:' not in launch, 'Workload launch failed')
                    reported_activity = launch_activity(launch)
                    time.sleep(.9)
                    top_activity = resumed_activity(device, package)
                    pid = device.shell('pidof ' + package, check=True).stdout.strip()
                    require(re.fullmatch(r'\d+', pid), 'Unique foreground app process not found')
                    group = device.shell('cat /proc/' + pid + '/cgroup; cat /proc/' + pid + '/cpuset', check=True)
                    transitions.append({'round': round_number, 'package': package,
                                        'elapsed_seconds': round(time.monotonic()-start, 3), 'launch': launch,
                                        'reported_activity': reported_activity,
                                        'launch_timing_valid_for_expected_app': reported_activity.split('/')[0] == package,
                                        'top_resumed_activity': top_activity,
                                        'pid': int(pid), 'foreground_cgroups': group.stdout.strip()})
            sampling_stop.set()
            if thread is not None:
                thread.join(timeout=12)
                require(not thread.is_alive() and all('error' not in item for item in samples), 'Frequency/memory sampler failed')
            report.update({'transitions': transitions, 'thermal_samples': thermal_samples,
                           'elapsed_seconds': round(time.monotonic()-start, 2), 'frames': {}})
            for package in packages:
                raw = device.shell('dumpsys gfxinfo ' + package + ' framestats', check=True).stdout
                (directory / (package + '-gfxinfo.txt')).write_text(raw)
                report['frames'][package] = frame_stats(raw)
            report['end_processes'] = {p: device.shell('pidof ' + p).stdout.strip() for p in packages}
            report['workload_processes_stable'] = report['start_processes'] == report['end_processes']
        report['after'] = snapshot(device, directory, 'after')
        report['completed'] = True
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        sampling_stop.set()
        if thread is not None:
            thread.join(timeout=12)
        report['sampling_stopped'] = thread is None or not thread.is_alive()
        (directory / 'samples.json').write_text(json.dumps(samples, indent=2) + '\n')
        try:
            if args.phase == 'switch':
                command = 'settings delete global stay_on_while_plugged_in' if setting == 'null' else 'settings put global stay_on_while_plugged_in ' + setting
                device.shell(command, check=True)
            report['stay_awake_restored'] = device.shell('settings get global stay_on_while_plugged_in', check=True).stdout.strip() == setting
            report['final_identity'] = identity(device)
            report['identities_stable'] = report['final_identity'] == before
        except Exception as exc:
            report['cleanup_error'] = str(exc)
            report['stay_awake_restored'] = False
            report['identities_stable'] = False
        try:
            log = device.shell('logcat -b main -b system -b crash -d -v threadtime -t 2500', timeout=30).stdout
            (directory / 'logcat-tail.txt').write_text(log)
        except Exception as exc:
            report['log_capture_error'] = str(exc)
        (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('UI performance capture: ' + str(directory / 'report.json') + '; completed=' + str(report['completed']), flush=True)
    if not report['completed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

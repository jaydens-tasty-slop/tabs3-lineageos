#!/usr/bin/env python3
"""Bounded foreground validation in the installed F-Droid apps; no camera tests."""
import argparse
import datetime
import hashlib
import http.server
import ipaddress
import json
import os
import pathlib
import re
import shlex
import socket
import subprocess
import threading
import time
import urllib.parse
import uuid
import xml.etree.ElementTree as ET

from adb_device import AdbDevice, private_directory
from device_smoke_common import file_hash, require

ROOT = pathlib.Path(__file__).resolve().parent.parent
BROWSER = "org.mozilla.fennec_fdroid"
STRESS = "net.tlfoxhuman.droidstress"


def keyguard_dismissed(policy):
    return ('mIsShowing=false' in policy or
            re.search(r'^\s*showing=false\s*$', policy, re.M) is not None)


def ui(device, directory, name):
    require(keyguard_dismissed(device.shell('dumpsys window policy', check=True).stdout),
            'Normal screen unlock required for UI capture')
    device.shell('uiautomator dump /data/local/tmp/tabs3-fdroid-validation-ui.xml', timeout=20, check=True)
    text = device.shell('cat /data/local/tmp/tabs3-fdroid-validation-ui.xml', check=True).stdout
    (directory / (name + '.xml')).write_text(text)
    return ET.fromstring(text)


def tap_node(device, node):
    match = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
    require(match is not None, 'Missing UI bounds')
    x1, y1, x2, y2 = map(int, match.groups())
    device.shell(f'input tap {(x1+x2)//2} {(y1+y2)//2}', check=True)


def thermal(device):
    raw = device.shell('dumpsys thermalservice', check=True).stdout
    current = raw.split('Current temperatures from HAL:', 1)[-1].split('Current cooling devices', 1)[0]
    values = [{'celsius': float(t), 'type': int(kind), 'name': name}
              for t, kind, name in re.findall(r'Temperature\{mValue=([0-9.]+), mType=(\d+), mName=([^,}]+)', current)]
    require(values and any(t['type'] == 0 for t in values), 'Fresh CPU temperatures unavailable')
    battery = device.shell('dumpsys battery', check=True).stdout
    match = re.search(r'^\s*temperature:\s*(\d+)\s*$', battery, re.M)
    require(match is not None, 'Battery temperature unavailable')
    battery_c = int(match.group(1)) / 10
    hottest = max(t['celsius'] for t in values if t['type'] in (0, 1))
    require(hottest < 85 and battery_c < 44 and all(t['celsius'] < 44 for t in values if t['type'] == 2)
            and all(t['celsius'] < 42 for t in values if t['type'] == 3), 'Temperature stop limit reached')
    return {'hal': values, 'battery_celsius': battery_c}


def exact_fennec_transparent_canvas_limit(final):
    """Recognize the bounded Firefox Android video-to-Canvas limitation."""
    videos = final.get('videos', [])
    return (final.get('completed') is True and not final.get('errors')
            and len(videos) == 2
            and all(test.get('passed') is True for test in final.get('tests', []))
            and len(final.get('tests', [])) == 6
            and all(video.get('supported') is True
                    and video.get('ended') is True
                    and video.get('media_error') is None
                    and video.get('current_time', 0) >= 19
                    and video.get('duration', 0) >= 19
                    and video.get('width') == 1920
                    and video.get('height') == 1080
                    and video.get('frame_callbacks', 0) >= 200
                    and video.get('total_video_frames') == 1200
                    and isinstance(video.get('dropped_frames'), int)
                    and video['dropped_frames'] <= 120
                    and len(video.get('pixel_samples', [])) >= 3
                    and all(sample.get('coarse_color_check_passed') is False
                            and sample.get('quadrants') == [[0, 0, 0, 0]] * 4
                            for sample in video['pixel_samples'])
                    for video in videos))


def browser(device, directory, report, args):
    browser_package = args.browser_package
    matches = re.findall(r'\binet (\d+\.\d+\.\d+\.\d+/\d+)\b', device.shell('ip -4 addr show dev wlan0', check=True).stdout)
    require(len(matches) == 1, 'Connected IPv4 Wi-Fi required')
    interface = ipaddress.ip_interface(matches[0]); peer = str(interface.ip)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
        route.connect((peer, 9)); bind = route.getsockname()[0]
    require(ipaddress.ip_address(bind) in interface.network, 'Host must share tablet LAN')
    require('dev wlan0' in device.shell('ip route get ' + bind, check=True).stdout, 'LAN route must use Wi-Fi')
    fixture = ROOT / 'device-validation/browser/index.html'
    media = ROOT / 'artifacts/device-media-stress-fixtures-v1'
    metadata = json.loads((media / 'manifest.json').read_text())
    names = ('avc-high-1080p60-moving', 'hevc-main-1080p60-moving')
    cases = {c['name']: c for c in metadata['cases'] if c['name'] in names}
    for item in cases.values():
        require(file_hash(media / item['file']) == item['sha256'], 'Synthetic video fixture changed')
    events = []; requests = []; token = uuid.uuid4().hex
    active_video = {'name': None}; decoder_observations = {name: [] for name in names}
    report.update({'transport': 'wifi', 'browser_package': browser_package,
                   'browser_suite': args.browser_suite,
                   'fixture_sha256': file_hash(fixture), 'video_fixtures': cases})
    descriptors_command = 'ls -l /proc/[0-9]*/fd/* 2>/dev/null | grep " /dev/video32$"'
    observer_uid = device.shell('id -u', check=True).stdout.strip()
    if observer_uid != '0':
        root = device.shell('su 0 id -u')
        if root.returncode == 0 and root.stdout.strip() == '0':
            descriptors_command = 'su 0 sh -c ' + shlex.quote(descriptors_command)
            observer_uid = '0'
    report['decoder_descriptor_observer_uid'] = observer_uid
    report['decoder_observer_scope'] = 'Read-only Venus descriptor observation; browser itself retains its ordinary application UID. Missing observations alone do not establish software decoding.'

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *values):
            pass

        def accepted(self):
            if self.client_address[0] != peer:
                self.send_error(403); return False
            return True

        def do_GET(self):
            if not self.accepted(): return
            path = urllib.parse.urlsplit(self.path).path
            requests.append({'path': path, 'user_agent': self.headers.get('User-Agent'), 'time': time.monotonic()})
            if path == '/':
                payload = fixture.read_bytes(); mime = 'text/html; charset=utf-8'
            elif path.startswith('/media/') and path[7:] in [c['file'] for c in cases.values()]:
                payload = (media / path[7:]).read_bytes(); mime = 'video/mp4'
            else:
                self.send_error(404); return
            start, end = 0, len(payload)-1; ranged = self.headers.get('Range')
            if ranged:
                match = re.fullmatch(r'bytes=(\d+)-(\d*)', ranged)
                if not match: self.send_error(416); return
                start = int(match.group(1)); end = min(end, int(match.group(2))) if match.group(2) else end
                if start > end: self.send_error(416); return
            self.send_response(206 if ranged else 200)
            self.send_header('Content-Type', mime); self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Cache-Control', 'no-store')
            if ranged: self.send_header('Content-Range', f'bytes {start}-{end}/{len(payload)}')
            self.send_header('Content-Length', str(end-start+1)); self.end_headers()
            try: self.wfile.write(payload[start:end+1])
            except (BrokenPipeError, ConnectionResetError): pass

        def do_POST(self):
            if not self.accepted(): return
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            length = int(self.headers.get('Content-Length', '0'))
            if query.get('run') != [token] or not 0 < length <= 131072:
                self.send_error(400); return
            try: event = json.loads(self.rfile.read(length))
            except ValueError: self.send_error(400); return
            events.append(event)
            if event.get('kind') == 'video-start': active_video['name'] = event.get('name')
            if event.get('kind') == 'video-end': active_video['name'] = None
            (directory / 'browser-events.json').write_text(json.dumps(events, indent=2) + '\n')
            self.send_response(200); self.send_header('Content-Length', '2'); self.end_headers(); self.wfile.write(b'ok')

    server = http.server.ThreadingHTTPServer((bind, args.port), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        endpoint = f'http://{bind}:{args.port}/?run={token}'; report['endpoint'] = endpoint
        device.shell('am start -W -a android.intent.action.VIEW -d ' + shlex.quote(endpoint) + ' -p ' + browser_package, check=True)
        deadline = time.monotonic() + 180; onboarding = 0; observations = []
        while time.monotonic() < deadline and not any(e.get('kind') in ('complete', 'failure') for e in events):
            observations.append(thermal(device))
            if not events and onboarding < 8:
                tree = ui(device, directory, 'browser-onboarding-' + str(onboarding))
                buttons = [n for n in tree.iter('node') if n.get('package') == browser_package
                           and n.get('text', '').lower() in ('start browsing', 'not now', 'skip')]
                default_prompt = any(n.get('package') == 'com.android.permissioncontroller'
                                     and n.get('text') == 'Set Fennec as your default browser app?'
                                     for n in tree.iter('node'))
                if default_prompt:
                    buttons = [n for n in tree.iter('node') if n.get('package') == 'com.android.permissioncontroller'
                               and n.get('resource-id') == 'android:id/button2' and n.get('text') == 'Cancel']
                http_prompt = browser_package == 'de.baumann.browser' and any(
                    n.get('package') == browser_package and n.get('text', '').startswith('Website uses unsecured connection')
                    for n in tree.iter('node'))
                if http_prompt:
                    # Confirm HTTP only for this generated LAN fixture. Do not
                    # select the global Never option or relaunch the same URL.
                    confirmations = [n for n in tree.iter('node') if n.get('package') == browser_package
                                     and n.get('text') == 'http://'
                                     and n.get('resource-id') == browser_package + ':id/menuEntry'
                                     and n.get('enabled') == 'true']
                    require(len(confirmations) == 1, 'Unique local-fixture HTTP confirmation not found')
                    tap_node(device, confirmations[0])
                    report['local_fixture_http_confirmed'] = True
                elif buttons:
                    tap_node(device, buttons[-1])
                    device.shell('am start -W -a android.intent.action.VIEW -d ' + shlex.quote(endpoint) + ' -p ' + browser_package, check=True)
                onboarding += 1
            name = active_video['name']
            if name in decoder_observations:
                descriptors = device.shell(descriptors_command, timeout=15).stdout
                if descriptors: decoder_observations[name].append(descriptors)
                screenshot = directory / (name + '-screen.png')
                if len(decoder_observations[name]) >= 3 and not screenshot.exists():
                    capture = subprocess.run(device.command + ['exec-out', 'screencap', '-p'], capture_output=True, timeout=20)
                    require(capture.returncode == 0 and capture.stdout.startswith(b'\x89PNG\r\n\x1a\n'), 'Screen capture failed')
                    screenshot.write_bytes(capture.stdout)
            time.sleep(1)
        final = next((e for e in reversed(events) if e.get('kind') == 'complete'), None)
        report.update({'browser_result': final, 'decoder_observations': decoder_observations,
                       'temperature_samples': observations, 'requests': requests})
        require(final is not None, 'No completed browser result before deadline; inspect onboarding evidence')
        expected_agent = 'Firefox/' if browser_package == BROWSER else 'Chrome/'
        require(expected_agent in final.get('user_agent', ''), 'Unexpected browser engine in result')
        for video in final.get('videos', []):
            if video.get('passed'):
                video['hardware_decoder_observed'] = bool(decoder_observations[video['name']])
        report['fixture_native_passed'] = final.get('passed') is True
        known_limit = False
        if args.accept_fennec_transparent_video_canvas:
            require(browser_package == BROWSER,
                    'The transparent-Canvas allowance is scoped only to Fennec')
            known_limit = exact_fennec_transparent_canvas_limit(final)
            report['known_fennec_transparent_canvas_limit_observed'] = known_limit
            report['known_limitation_scope'] = (
                'Both generated videos completed with bounded drops and no media error; '
                'only Firefox video-to-Canvas readback returned transparent pixels. '
                'This does not establish per-frame hardware decoding.')
        report['fixture_passed'] = report['fixture_native_passed'] or known_limit
        if args.browser_suite == 'fixture':
            report['public_https_pages_skipped'] = True
            require(report['fixture_passed'], 'Generated browser fixture checks failed')
            return
        # Public pages use browser DNS/TLS, with no accounts or personal forms.
        public = []
        for i, url in enumerate(('https://example.com/', 'https://www.wikipedia.org/', 'https://f-droid.org/')):
            if browser_package == 'de.baumann.browser':
                tree = ui(device, directory, 'before-public-page-' + str(i))
                local_warning = any(n.get('package') == browser_package
                                    and n.get('text', '').startswith('Website uses unsecured connection')
                                    for n in tree.iter('node'))
                local_host = any(n.get('package') == browser_package and n.get('text') == bind
                                 for n in tree.iter('node'))
                if local_warning and local_host:
                    cancel = [n for n in tree.iter('node') if n.get('package') == browser_package
                              and n.get('resource-id') == browser_package + ':id/menuCancel'
                              and n.get('text') == 'Cancel']
                    require(len(cancel) == 1, 'Unique local-fixture dialog cancel not found')
                    tap_node(device, cancel[0])
                    report.setdefault('local_fixture_dialog_cancelled_before_public', []).append(i)
            device.shell('am start -W -a android.intent.action.VIEW -d ' + shlex.quote(url) + ' -p ' + browser_package, check=True)
            time.sleep(6)
            tree = ui(device, directory, 'public-page-' + str(i))
            text = ' '.join(n.get('text', '') + ' ' + n.get('content-desc', '') for n in tree.iter('node'))
            expected = ('Example Domain', 'Wikipedia', 'F-Droid')[i]
            public.append({'url': url, 'expected_text_seen': expected.lower() in text.lower(),
                           'error_page_seen': any(s in text.lower() for s in ('secure connection failed', 'server not found', 'unable to connect'))})
        report['public_pages'] = public
        report['public_https_pages_passed'] = all(p['expected_text_seen'] and not p['error_page_seen'] for p in public)
        require(report['fixture_passed'] and report['public_https_pages_passed'], 'Browser fixture or public HTTPS checks failed')
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
        report['server_stopped'] = not thread.is_alive()


def stress(device, directory, report, args):
    device.shell('pm grant ' + STRESS + ' android.permission.POST_NOTIFICATIONS', check=True)
    report.update({'stress_package': STRESS, 'threads': args.threads, 'memory_mib': args.memory_mib,
                   'minutes': args.minutes, 'temperature_samples': []})
    device.shell('am start -W -n ' + STRESS + '/.MainActivity', check=True)
    time.sleep(2)
    for resource, value in (('threadsInput', args.threads), ('durationInput', args.minutes), ('memstressInput', args.memory_mib)):
        tree = ui(device, directory, 'configure-' + resource)
        nodes = [n for n in tree.iter('node') if n.get('resource-id') == STRESS + ':id/' + resource]
        require(len(nodes) == 1, 'Missing stress input ' + resource)
        tap_node(device, nodes[0]); device.shell('input keyevent KEYCODE_MOVE_END; input keyevent --longpress KEYCODE_DEL', check=True)
        # Numeric inputs start with short defaults; delete the existing digits.
        device.shell('input keyevent KEYCODE_DEL KEYCODE_DEL KEYCODE_DEL KEYCODE_DEL; input text ' + str(value), check=True)
    device.shell('input keyevent KEYCODE_BACK', check=True)
    tree = ui(device, directory, 'stress-configured')
    for resource, value in (('threadsInput', args.threads), ('durationInput', args.minutes), ('memstressInput', args.memory_mib)):
        nodes = [n for n in tree.iter('node') if n.get('resource-id') == STRESS + ':id/' + resource]
        require(len(nodes) == 1 and nodes[0].get('text') == str(value), 'Stress input readback differs')
    nodes = [n for n in tree.iter('node') if n.get('resource-id') == STRESS + ':id/startbutton']
    require(len(nodes) == 1 and nodes[0].get('text', '').lower() == 'start', 'Stress app is not idle')
    tap_node(device, nodes[0]); started = time.monotonic()
    identity = device.shell('pidof ' + STRESS, check=True).stdout.strip()
    require(re.fullmatch(r'\d+', identity), 'Missing unique stress process')
    before = device.shell('cat /proc/' + identity + '/stat', check=True).stdout
    report['stress_pid'] = int(identity)
    while time.monotonic()-started < args.minutes * 60 + 10:
        state = device.shell('dumpsys activity services ' + STRESS, check=True).stdout
        running = 'StressService' in state
        elapsed = time.monotonic()-started
        report['temperature_samples'].append({'elapsed_seconds': round(elapsed, 2), **thermal(device), 'service_running': running})
        require(device.shell('pidof ' + STRESS, check=True).stdout.strip() == identity, 'Stress process restarted')
        if not running:
            require(elapsed >= args.minutes * 60 - 3, 'Stress service stopped early')
            break
        time.sleep(4)
    else:
        raise ValueError('Stress service failed to stop after its timer')
    after = device.shell('cat /proc/' + identity + '/stat', check=True).stdout
    def ticks(text):
        fields = text[text.rfind(')')+2:].split()
        return int(fields[11]) + int(fields[12])
    report['cpu_ticks_consumed'] = ticks(after)-ticks(before)
    report['elapsed_seconds'] = round(time.monotonic()-started, 2)
    report['timer_stopped_service'] = True
    require(report['cpu_ticks_consumed'] > args.minutes * 600, 'Insufficient observed CPU work')
    tree = ui(device, directory, 'stress-finished')
    report['finished_ui'] = [{'id': n.get('resource-id'), 'text': n.get('text')} for n in tree.iter('node')
                             if n.get('resource-id') in (STRESS + ':id/startbutton', STRESS + ':id/statusText')]


def inventory(device, directory, report):
    report['app_launches'] = []
    launches = (('com.kgurgul.cpuinfo', '.HostActivity'),
                ('org.fdroid.fdroid', '.views.main.MainActivity'))
    for i, (package, activity_class) in enumerate(launches):
        require(device.shell('pm path ' + package).stdout.strip(), 'Inventory app missing')
        launched = device.shell('am start -W -n ' + package + '/' + activity_class)
        (directory / (package + '-launch.txt')).write_text(launched.stdout + '\nSTDERR:\n' + launched.stderr)
        require(launched.returncode == 0 and 'Error:' not in launched.stdout, 'Inventory app launch failed')
        time.sleep(6)
        pid = device.shell('pidof ' + package, check=True).stdout.strip()
        require(re.fullmatch(r'\d+', pid), 'Missing unique app process')
        tree = ui(device, directory, package + '-initial')
        strings = [n.get('text') or n.get('content-desc') for n in tree.iter('node')
                   if n.get('package') == package and (n.get('text') or n.get('content-desc'))]
        activity = device.shell('dumpsys activity activities', check=True).stdout
        resumed = any(package in line for line in activity.splitlines()
                      if 'topResumedActivity' in line or 'mResumedActivity' in line)
        require(strings and resumed, 'App did not expose a resumed screen with text')
        time.sleep(6)
        stable = device.shell('pidof ' + package, check=True).stdout.strip() == pid
        require(stable, 'Inventory app process restarted')
        item = {'package': package, 'pid': int(pid), 'resumed': resumed,
                'ui_text': strings, 'process_stable': stable, 'scope': 'Initial screen launch and rendering'}
        report['app_launches'].append(item)
    report['inventory_launches_passed'] = True


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--phase', choices=('browser', 'stress', 'inventory'), required=True)
    parser.add_argument('--browser-package', choices=(BROWSER, 'de.baumann.browser'), default=BROWSER)
    parser.add_argument('--browser-suite', choices=('full', 'fixture'), default='full',
                        help='Fixture runs omit public sites and record that narrower scope')
    parser.add_argument('--accept-fennec-transparent-video-canvas', action='store_true',
                        help='Accept only the exact documented Fennec transparent video-to-Canvas profile')
    parser.add_argument('--wait-unlock-seconds', type=int, default=300)
    parser.add_argument('--port', type=int, default=18024)
    parser.add_argument('--minutes', type=int, default=2)
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--memory-mib', type=int, default=0)
    args = parser.parse_args()
    require(30 <= args.wait_unlock_seconds <= 600 and 1024 <= args.port <= 65535, 'Use bounded wait and unprivileged port')
    require(1 <= args.minutes <= 3 and 1 <= args.threads <= 4 and 0 <= args.memory_mib <= 32, 'Use a light, bounded stress workload')
    device = AdbDevice(args.serial)
    require(not device.recovery and device.props.get('ro.build.version.sdk') == '37' and device.props.get('sys.boot_completed') == '1', 'Booted Android 17 required')
    require('USB powered: true' in device.shell('dumpsys battery', check=True).stdout, 'USB power required')
    package = args.browser_package if args.phase == 'browser' else STRESS if args.phase == 'stress' else 'com.kgurgul.cpuinfo'
    require(device.shell('pm path ' + package).stdout.strip(), 'F-Droid app is not installed')
    setting = device.shell('settings get global stay_on_while_plugged_in', check=True).stdout.strip()
    require(setting == 'null' or re.fullmatch(r'\d+', setting), 'Unexpected USB stay-awake setting')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = private_directory(ROOT / 'diagnostics' / (stamp + '-fdroid-' + args.phase + '-' + uuid.uuid4().hex[:8]))
    report = {'serial': args.serial, 'phase': args.phase, 'passed': False, 'stay_awake_original': setting,
              'limits': ['Bounded tests do not establish long-term thermal endurance or memory correctness',
                         'No camera, account login or personal media tests', 'F-Droid apps are retained for the owner']}
    report['harness_sha256'] = file_hash(pathlib.Path(__file__))
    (output / 'harness.py').write_bytes(pathlib.Path(__file__).read_bytes())
    identity_command = 'pidof system_server; pidof com.android.networkstack.process; cat /proc/sys/kernel/random/boot_id'
    changed = False
    try:
        changed = True; device.shell('svc power stayon usb', check=True)
        require(device.shell('settings get global stay_on_while_plugged_in', check=True).stdout.strip() == '2', 'USB stay-awake was not applied')
        print('Waiting for normal unlock; USB stay-awake active: ' + str(output), flush=True)
        deadline = time.monotonic()+args.wait_unlock_seconds
        while not (keyguard_dismissed(device.shell('dumpsys window policy', check=True).stdout)
                   and device.shell('am get-started-user-state 0', check=True).stdout.strip() == 'RUNNING_UNLOCKED'):
            require(time.monotonic() < deadline, 'Normal unlock was not observed')
            time.sleep(1)
        report['framework_before'] = device.shell(identity_command, check=True).stdout
        device.shell('dumpsys package ' + package, check=True).stdout
        report['temperature_before'] = thermal(device)
        if args.phase == 'browser':
            browser(device, output, report, args)
        elif args.phase == 'stress':
            stress(device, output, report, args)
        else:
            inventory(device, output, report)
        report['framework_after'] = device.shell(identity_command, check=True).stdout
        report['framework_unchanged'] = report['framework_before'] == report['framework_after']
        report['passed'] = report['framework_unchanged']
    except Exception as error:
        report['error'] = str(error)
    finally:
        if 'framework_before' in report:
            try:
                report['framework_after'] = device.shell(identity_command, check=True).stdout
                report['framework_unchanged'] = report['framework_before'] == report['framework_after']
                report['passed'] = report['passed'] and report['framework_unchanged']
            except Exception as error:
                report['passed'] = False; report['identity_error'] = str(error)
        if args.phase == 'stress':
            try:
                device.shell('am force-stop ' + STRESS, check=True)
                report['stress_cleanup'] = 'StressService' not in device.shell('dumpsys activity services ' + STRESS, check=True).stdout
            except Exception as error:
                report['stress_cleanup'] = False; report['cleanup_error'] = str(error)
            report['passed'] = report['passed'] and report['stress_cleanup']
        if changed:
            try:
                command = 'settings delete global stay_on_while_plugged_in' if setting == 'null' else 'settings put global stay_on_while_plugged_in ' + setting
                device.shell(command, check=True)
                report['stay_awake_restored'] = device.shell('settings get global stay_on_while_plugged_in', check=True).stdout.strip() == setting
            except Exception as error:
                report['stay_awake_restored'] = False; report['restore_error'] = str(error)
            report['passed'] = report['passed'] and report['stay_awake_restored']
        for label, command in (('crash-buffer', 'logcat -b crash -d -v threadtime'), ('app-exit-info', 'dumpsys activity exit-info ' + package)):
            try: (output / (label + '.txt')).write_text(device.shell(command, check=True).stdout)
            except Exception: pass
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('F-Droid validation: ' + str(output / 'report.json') + '; passed=' + str(report['passed']), flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()

"""Install and repeatedly execute a LeanCLR APK on the authorized MuMu device."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('apk', type=Path)
parser.add_argument('--sample', choices=['dotnet', 'semantics', 'extended'], default='dotnet')
parser.add_argument('--device', default='localhost:7555')
parser.add_argument('--runs', type=int, default=3)
parser.add_argument('--require-aot', action='store_true')
parser.add_argument('--report-dir', type=Path)
args = parser.parse_args()
adb = ROOT / '.tools/android-sdk/platform-tools/adb.exe'
output = args.report_dir or ROOT / 'build/android' / ('validation-' + args.sample)
output.mkdir(parents=True, exist_ok=True)


def call(*command, binary=False):
    return subprocess.check_output([str(adb), '-s', args.device, *command],
                                   text=not binary, encoding=None if binary else 'utf-8', errors=None if binary else 'replace')


subprocess.run([str(adb), 'connect', args.device], check=True)
with zipfile.ZipFile(args.apk) as package:
    libraries = sorted(name for name in package.namelist() if name.startswith('lib/') and name.endswith('.so'))
    assert libraries == ['lib/x86_64/libc++_shared.so', 'lib/x86_64/libgodot_android.so'], libraries
call('install', '-r', str(args.apk.resolve()))
package = 'com.focuscreative.leanclrgodot.' + args.sample
activity = call('shell', 'cmd', 'package', 'resolve-activity', '--brief', package).strip().splitlines()[-1]
runs = []
for index in range(args.runs):
    call('shell', 'am', 'force-stop', package)
    call('logcat', '-c')
    start = time.monotonic()
    call('shell', 'am', 'start', '-W', '-n', activity)
    marker = {'semantics': 'M2_SEMANTICS_OK checks=15 observed=31', 'extended': 'M5_EXTENDED_OK checks=11', 'dotnet': 'NODE2D_SMOKE_OK'}[args.sample]
    while time.monotonic() - start < 60:
        log = call('logcat', '-d', '-v', 'brief', 'godot:V', 'DEBUG:F', 'libc:F', 'AndroidRuntime:E', '*:S')
        completed = marker in log and (not args.require_aot or 'LEANCLR_AOT_HOTCALL module=DemoLogic step=4 benchmark=0' in log)
        if completed or 'Fatal signal' in log or 'FATAL EXCEPTION' in log or 'LEANCLR_GODOT_FATAL' in log:
            break
        time.sleep(.5)
    (output / f'run-{index}.log').write_text(log, encoding='utf-8')
    assert 'LEANCLR_GODOT_READY backend=LeanCLR' in log and marker in log, log[-5000:]
    assert not any(text in log for text in ['Fatal signal', 'FATAL EXCEPTION', 'LEANCLR_GODOT_CALLBACK_FAILED', 'resources still in use', 'ObjectDB instances leaked'])
    if args.sample == 'dotnet':
        assert 'instances=1 frames=4 x=8 speed=120' in log, log[-3000:]
    if args.require_aot:
        assert 'LEANCLR_AOT_HOTCALL module=DemoLogic step=4 benchmark=0' in log
    runs.append({'elapsed_seconds': time.monotonic() - start, 'markers': [line for line in log.splitlines() if any(m in line for m in ['LEANCLR_', 'M2_', 'NODE2D_'])]})
report = {'status': 'passed', 'device': args.device, 'api': call('shell', 'getprop', 'ro.build.version.sdk').strip(),
          'native_abi': call('shell', 'getprop', 'ro.product.cpu.abi').strip(), 'libraries': libraries,
          'apk_sha256': hashlib.sha256(args.apk.read_bytes()).hexdigest(), 'runs': runs}
(output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print('ANDROID_RUNTIME_OK', args.sample, len(runs), 'fresh processes')

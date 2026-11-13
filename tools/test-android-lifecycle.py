"""Verify visible rendering, background/foreground survival and cold recreation on MuMu."""
import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.tools/browser'))
from PIL import Image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('apk', type=Path)
parser.add_argument('--device', default='localhost:7555')
args = parser.parse_args()
adb = ROOT / '.tools/android-sdk/platform-tools/adb.exe'
output = ROOT / 'build/android/lifecycle'
output.mkdir(parents=True, exist_ok=True)
package = 'com.focuscreative.leanclrgodot.dotnet'
activity = package + '/com.godot.game.GodotAppLauncher'


def call(*command, binary=False):
    return subprocess.check_output([str(adb), '-s', args.device, *command], text=not binary,
        encoding=None if binary else 'utf-8', errors=None if binary else 'replace', timeout=30)


def screenshot(name):
    data = call('exec-out', 'screencap', '-p', binary=True)
    (output / name).write_bytes(data)
    image = Image.open(io.BytesIO(data)).convert('RGB')
    points = [(index % image.width, index // image.width) for index, (r, g, b) in enumerate(image.getdata())
              if abs(r - 100) < 15 and abs(g - 149) < 15 and abs(b - 237) < 15]
    assert len(points) > 50, 'C# DrawCircle was not visible'
    return {'blue_pixels': len(points), 'centroid_x': sum(p[0] for p in points) / len(points)}


subprocess.run([str(adb), 'connect', args.device], check=True)
call('install', '-r', str(args.apk.resolve()))
call('shell', 'am', 'force-stop', package)
call('logcat', '-c')
call('shell', 'am', 'start', '-W', '-n', activity)
time.sleep(2)
before = screenshot('before.png')
pid = call('shell', 'pidof', package).strip()
call('shell', 'input', 'keyevent', '3')
time.sleep(1)
call('shell', 'am', 'start', '-W', '-n', activity)
time.sleep(1)
assert call('shell', 'pidof', package).strip() == pid, 'Foreground restart unexpectedly recreated the process'
after = screenshot('after-resume.png')
log = call('logcat', '-d', '-v', 'brief')
assert log.count('LEANCLR_GODOT_READY backend=LeanCLR') == 1
assert 'LEANCLR_GODOT_FATAL' not in log and 'Fatal signal' not in log
(output / 'resume.log').write_text(log, encoding='utf-8')
call('shell', 'am', 'force-stop', package)
call('logcat', '-c')
call('shell', 'am', 'start', '-W', '-n', activity)
time.sleep(2)
new_pid = call('shell', 'pidof', package).strip()
assert new_pid != pid
recreated = screenshot('recreated.png')
log = call('logcat', '-d', '-v', 'brief')
assert 'LEANCLR_GODOT_READY backend=LeanCLR' in log and 'LEANCLR_GODOT_FATAL' not in log
(output / 'recreated.log').write_text(log, encoding='utf-8')
call('shell', 'am', 'force-stop', package)
(output / 'report.json').write_text(json.dumps({'status': 'passed', 'same_process_resume': True,
    'fresh_process_recreated': True, 'before': before, 'after_resume': after, 'recreated': recreated}, indent=2) + '\n', encoding='utf-8')
print('ANDROID_LIFECYCLE_OK visible=true resume=true recreation=true')

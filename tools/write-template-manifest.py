"""Snapshot a built template and its exact publication ABI into the local SDK cache."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = {'win64': 'extern/godot/bin/godot.windows.template_release.x86_64.leanclr_m1.mono.exe',
             'html5': 'extern/godot/bin/godot.web.template_release.wasm32.nothreads.leanclr_m3.mono.zip',
             'android': 'build/android/leanclr-debug.apk'}
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('target', choices=TEMPLATES)
parser.add_argument('--mode', choices=['interpreter', 'mixed'], default='interpreter')
parser.add_argument('--runtime-source', type=Path, default=ROOT / 'extern/leanclr')
args = parser.parse_args()
source = ROOT / TEMPLATES[args.target]
destination = ROOT / 'build/sdk/templates' / args.target / args.mode
destination.mkdir(parents=True, exist_ok=True)
files = [source]
if args.target == 'win64':
    files.append(source.with_name(source.name.replace('.exe', '.console.exe')))
digests = {}
for file in files:
    shutil.copyfile(file, destination / file.name)
    digests[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
lock = json.loads((ROOT / 'dependencies.json').read_text(encoding='utf-8'))
commit = subprocess.check_output(['git', '-c', 'core.fsmonitor=false', '-C', str(args.runtime_source), 'rev-parse', 'HEAD'], text=True).strip()
report = {'schema': 1, 'target': args.target, 'abi': 'wasm32' if args.target == 'html5' else 'x86_64',
          'pointer_bits': 32 if args.target == 'html5' else 64, 'real_bits': 32, 'mode': args.mode,
          'dependencies': lock, 'runtime_source_commit': commit, 'files': digests,
          'godotsharp_sha256': hashlib.sha256((ROOT / 'build/m1/managed/GodotSharp/bin/Release/net10.0/GodotSharp.dll').read_bytes()).hexdigest(),
          'calli_sha256': hashlib.sha256((ROOT / 'build/m1/calli/calli_bridges.json').read_bytes()).hexdigest()}
if args.mode == 'mixed':
    report['aot'] = json.loads((ROOT / 'build/m5/aot-manifest.json').read_text(encoding='utf-8'))
if args.target == 'android':
    report['runtime_patches'] = json.loads((ROOT / 'build/android/leanclr-source/patches.json').read_text(encoding='utf-8'))
(destination / 'template.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print('SDK_TEMPLATE_READY', destination)

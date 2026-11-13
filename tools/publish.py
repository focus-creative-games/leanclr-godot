"""Single entry point for the bounded Windows/HTML5/Android LeanCLR publication SDK."""
import argparse
import atexit
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--target', choices=['win64', 'html5', 'android'], required=True)
parser.add_argument('--sample', type=Path, default=ROOT / 'samples/dotnet')
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--runtime-source', type=Path, default=ROOT / 'extern/leanclr')
parser.add_argument('--build', action='store_true', help='Rebuild the target template as well as managed code')
parser.add_argument('--experimental', action='store_true', help='Allow pending application profiles, still reject known unsupported dependencies')
parser.add_argument('--smoke', action='store_true', help='Embed deterministic test arguments in Android APK')
parser.add_argument('--aot', action='store_true', help='Use the exact compiled DemoLogic module with interpreter fallback for other assemblies')
args = parser.parse_args()
sample = args.sample.resolve()
output = args.output.resolve()
if not (sample / '.godot/mono').is_dir():
    raise SystemExit('Build and import this project with the official .NET editor before publishing; development script metadata is missing.')
if output.exists():
    raise SystemExit('Output must be a new directory; existing publications are preserved.')
if ROOT not in output.parents or ROOT / 'samples' in output.parents:
    raise SystemExit('Choose a new output directory inside this repository, outside samples.')
# Managed compilation and the private import cache are shared. Fail clearly
# rather than racing two editor menu requests over those build products.
lock_path = ROOT / 'build/sdk/publisher.lock'
lock_path.parent.mkdir(parents=True, exist_ok=True)
publication_lock = lock_path.open('a+b')
if lock_path.stat().st_size == 0:
    publication_lock.write(b'\0')
    publication_lock.flush()
publication_lock.seek(0)
try:
    msvcrt.locking(publication_lock.fileno(), msvcrt.LK_NBLCK, 1)
except OSError:
    raise SystemExit('Another LeanCLR publication is active; retry after it completes.')
atexit.register(publication_lock.close)
stage = output.with_name(output.name + '.staging-' + uuid.uuid4().hex[:8])
stage.mkdir(parents=True)
log = (stage / 'pipeline.log').open('w', encoding='utf-8')


def run(command):
    result = subprocess.run(list(map(str, command)), cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    log.flush()
    if result.returncode:
        raise RuntimeError('Publication failed; preserved diagnostics: ' + str(stage))


lock = json.loads((ROOT / 'dependencies.json').read_text(encoding='utf-8'))
runtime = args.runtime_source.resolve()
commit = subprocess.check_output(['git', '-c', 'core.fsmonitor=false', '-C', str(runtime), 'rev-parse', 'HEAD'], text=True).strip()
if commit != lock['leanclr']['commit']:
    raise SystemExit('Runtime revision mismatch. Update and validate dependencies.json before publishing.')
run(['python', ROOT / 'tools/prepare_m0_exporter.py'])
run(['python', ROOT / 'tools/prepare_m1_managed.py', '--sample', sample])
if args.build:
    script = {'win64': 'build-m1.ps1', 'html5': 'build-web-runtime.ps1', 'android': 'build-android-runtime.ps1'}[args.target]
    command = ['powershell', '-NoProfile', '-File', ROOT / 'tools' / script, '-RuntimeSource', runtime]
    if args.target == 'win64':
        command += ['-Sample', sample]
    if args.aot:
        command.append('-Aot')
    run(command)
mode = 'mixed' if args.aot else 'interpreter'
template_dir = ROOT / 'build/sdk/templates' / args.target / mode
template_manifest = json.loads((template_dir / 'template.json').read_text(encoding='utf-8'))
if template_manifest['dependencies'] != lock or template_manifest['mode'] != mode or template_manifest['runtime_source_commit'] != commit:
    raise RuntimeError('Template version mismatch; rebuild the SDK template.')
for name, digest in template_manifest['files'].items():
    if hashlib.sha256((template_dir / name).read_bytes()).hexdigest() != digest:
        raise RuntimeError('Corrupted template: ' + name)
godotsharp = ROOT / 'build/m1/managed/GodotSharp/bin/Release/net10.0/GodotSharp.dll'
if hashlib.sha256(godotsharp.read_bytes()).hexdigest() != template_manifest['godotsharp_sha256']:
    raise RuntimeError('GodotSharp publication ABI mismatch; rebuild the SDK template.')
if args.aot:
    logic = ROOT / 'build/m1/managed/DemoLogic/bin/Release/net10.0/DemoLogic.dll'
    if hashlib.sha256(logic.read_bytes()).hexdigest() != template_manifest['aot']['aot_assembly_sha256']:
        raise RuntimeError('AOT assembly mismatch; regenerate and rebuild the mixed template.')
template = next(template_dir / name for name in template_manifest['files'] if '.console.' not in name)
command = ['python', ROOT / 'tools/publish-m1.py', '--target', {'win64': 'native', 'html5': 'web', 'android': 'android'}[args.target],
           '--sample', sample, '--runtime-source', runtime, '--output', stage, '--template', template]
if args.smoke:
    command.append('--smoke')
run(command)
manifest_path = stage / 'publication.json'
publication = json.loads(manifest_path.read_text(encoding='utf-8'))
publication['template_contract'] = template_manifest
manifest_path.write_text(json.dumps(publication, indent=2) + '\n', encoding='utf-8')
command = ['python', ROOT / 'tools/check-publication.py', stage / 'publication.json', '--sample', sample]
if args.experimental:
    command.append('--experimental')
run(command)
files = {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
         for p in stage.iterdir() if p.is_file() and p.name != 'pipeline.log'}
(stage / 'artifacts.json').write_text(json.dumps({'schema': 1, 'target': args.target, 'dependencies': lock,
    'pointer_bits': 32 if args.target == 'html5' else 64, 'real_bits': 32, 'mode': mode,
    'files': files}, indent=2) + '\n', encoding='utf-8')
log.close()
os.rename(stage, output)
print('LEANCLR_SDK_PUBLISHED', output)

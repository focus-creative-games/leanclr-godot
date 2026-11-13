"""Export and verify M0 Windows/Web artifacts using the private headless helper.

These artifacts exercise export policy and script identity; runtime_ready=false.
The verification process uses the official .NET runtime, not LeanCLR GodotSharp.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import os

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--helper', type=Path, default=ROOT / 'extern/godot/bin/godot.windows.editor.x86_64.leanclr_m0.mono.console.exe')
parser.add_argument('--runtime-source', type=Path, default=ROOT / 'extern/leanclr')
parser.add_argument('--godot-mono', type=Path, default=ROOT.parent / 'Godot_v4.7.2-stable_mono_win64')
args = parser.parse_args()
helper = args.helper.resolve()
if not (helper.parent / '._sc_').is_file():
    raise RuntimeError('Build the private self-contained helper with tools/build-m0-exporter.ps1 first.')
lock = json.loads((ROOT / 'dependencies.json').read_text(encoding='utf-8'))
sample = ROOT / 'samples/dotnet'
output = ROOT / 'build/m0/export'
output.mkdir(parents=True, exist_ok=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(project, arguments, log, env, marker=None, failure=None):
    command = [str(helper), '--headless', '--path', str(project), *arguments]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=180)
    text = result.stdout + result.stderr
    log.write_text(text, encoding='utf-8')
    if failure:
        if 'M0_EXPORT_PAYLOAD_OK' in text or failure not in text:
            raise RuntimeError(f'Expected rejection was not observed: {log}')
        print('M0_EXPORT_REJECT_OK', failure)
    elif result.returncode or (marker and marker not in text):
        raise RuntimeError(f'Export check failed: {log}\n{text[-4000:]}')
    return text


protected = [*sample.glob('*.cs'), *sample.glob('*.tscn'), sample / 'project.godot', sample / 'Gameplay.csproj',
             args.godot_mono / 'GodotSharp/Tools/GodotTools.dll']
before = {str(p): digest(p) for p in protected}
for target, preset, extension in [('native', 'M0 Windows baseline', 'exe'), ('wasm', 'M0 Web baseline', 'html')]:
    project = output / target / 'project'
    stage = output / target / 'payload'
    artifacts = output / target / 'artifacts'
    for directory in (project, stage, artifacts):
        directory.mkdir(parents=True, exist_ok=True)
    for pattern in ('*.cs', '*.uid', '*.tscn', '*.csproj', '*.sln', 'project.godot', 'NuGet.Config'):
        for source in sample.glob(pattern):
            shutil.copyfile(source, project / source.name)
    shutil.copytree(sample / '.godot/mono', project / '.godot/mono', dirs_exist_ok=True)
    presets = (sample / 'export_presets.cfg').read_text(encoding='utf-8')
    presets = presets.replace('res://../../build/templates', (ROOT / 'build/templates').as_posix())
    (project / 'export_presets.cfg').write_text(presets, encoding='utf-8')
    bcl = Path('C:/Program Files/dotnet/shared/Microsoft.NETCore.App/10.0.8') if target == 'native' else args.runtime_source / 'out/net10-runtime-win-x86/runtimes/win-x86/lib/net10.0'
    bindings = {'schema': 1, 'runtime_ready': False, 'scripts': [{'path': 'res://Player.cs', 'assembly': 'Gameplay',
                'type': 'Player', 'base': 'Godot.Node2D', 'uid': (sample / 'Player.cs.uid').read_text().strip()}]}
    payloads = {
        'Gameplay.dll.bytes': (sample / '.godot/mono/temp/bin/Debug/Gameplay.dll').read_bytes(),
        'GodotSharp.dll.bytes': (args.godot_mono / 'GodotSharp/Api/Debug/GodotSharp.dll').read_bytes(),
        'System.Private.CoreLib.dll.bytes': (bcl / 'System.Private.CoreLib.dll').read_bytes(),
        'System.Runtime.dll.bytes': (bcl / 'System.Runtime.dll').read_bytes(),
        'scripts.json': json.dumps(bindings, indent=2).encode(),
    }
    core_hash = hashlib.sha256(payloads['System.Private.CoreLib.dll.bytes']).hexdigest()
    if core_hash != lock['corelib'][target + '_sha256']:
        raise RuntimeError('Unverified target CoreLib')
    manifest = {'phase': 'M0-export-prototype', 'runtime_ready': False, 'target': target,
                'godot_commit': lock['godot']['commit'], 'leanclr_commit': lock['leanclr']['commit'], 'files': []}
    for name, data in payloads.items():
        (stage / name).write_bytes(data)
        manifest['files'].append({'path': 'res://.leanclr/' + name, 'source': name, 'sha256': hashlib.sha256(data).hexdigest()})
    manifest_path = stage / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    env = dict(os.environ, GODOT_LEANCLR_M0_STAGE=str(stage))
    run(project, ['--editor', '--import'], output / target / 'import.log', env)
    artifact = artifacts / ('probe.' + extension)
    run(project, ['--export-release', preset, str(artifact)], output / target / 'export.log', env, 'M0_EXPORT_PAYLOAD_OK target=' + target)
    pck = artifact.with_suffix('.pck')
    if not artifact.is_file() or not pck.is_file():
        raise RuntimeError('Missing platform export outputs')
    run(project, ['--script', str(ROOT / 'tests/m0/verify_export.gd'), '--', str(manifest_path), str(pck)],
        output / target / 'verify.log', env, 'M0_EXPORT_VERIFY_OK target=' + target)
    if target == 'wasm':
        data = (stage / 'scripts.json').read_bytes()
        try:
            (stage / 'scripts.json').write_bytes(data + b'corrupt')
            run(project, ['--export-pack', preset, str(artifacts / 'rejected-hash.pck')], output / target / 'reject-hash.log', env,
                failure='M0 payload hash mismatch')
        finally:
            (stage / 'scripts.json').write_bytes(data)
        wrong = dict(manifest, target='native')
        try:
            manifest_path.write_text(json.dumps(wrong), encoding='utf-8')
            run(project, ['--export-pack', preset, str(artifacts / 'rejected-target.pck')], output / target / 'reject-target.log', env,
                failure='M0 payload does not match')
        finally:
            manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        clean_env = dict(os.environ)
        clean_env.pop('GODOT_LEANCLR_M0_STAGE', None)
        text = run(project, ['--export-release', preset, str(artifacts / 'rejected-no-stage.html')], output / target / 'reject-no-stage.log', clean_env,
                   failure='failed')
        if 'M0_EXPORT_PAYLOAD_OK' in text or 'failed' not in text.lower():
            raise RuntimeError('The private helper did not retain native Web rejection without an explicit stage')
        print('M0_EXPORT_REJECT_OK no-stage')
    print('M0_EXPORT_OK', target, artifact)
after = {str(p): digest(p) for p in protected}
if before != after:
    raise RuntimeError('Development source or installed official editor was modified')
(output / 'validation.json').write_text(json.dumps({'status': 'passed', 'runtime_ready': False, 'dependencies': lock,
    'helper_sha256': digest(helper.with_name(helper.name.replace('.console.exe', '.exe'))), 'protected_files': after}, indent=2) + '\n', encoding='utf-8')
print('M0_EXPORT_ALL_OK development sources and installed editor unchanged')

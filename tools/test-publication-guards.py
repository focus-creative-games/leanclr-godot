"""Verify conservative publication gates and fail-fast template/payload mismatch handling."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--publication', type=Path, required=True, help='A successful Win64 Node2D SDK publication')
parser.add_argument('--aot-template', type=Path)
args = parser.parse_args()
output = ROOT / 'build/sdk/guards'
output.mkdir(parents=True, exist_ok=True)
results = []


def run(command, name, env=None):
    result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=180)
    text = result.stdout + result.stderr
    (output / (name + '.log')).write_text(text, encoding='utf-8')
    return result.returncode, text


publication = json.loads((args.publication / 'publication.json').read_text(encoding='utf-8'))
probe = output / 'unsupported'
probe.mkdir(exist_ok=True)
(probe / 'Gameplay.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>', encoding='utf-8')
(probe / 'Probe.cs').write_text('public static class Probe { public static void Unsupported() { new System.Threading.Thread(() => {}).Start(); } }', encoding='utf-8')
code, text = run(['dotnet', 'build', probe / 'Gameplay.csproj', '-c', 'Release', '--nologo'], 'compile-unsupported')
assert code == 0, text
negative = dict(publication)
negative['assemblies'] = [{'path': str(probe / 'bin/Release/net10.0/Gameplay.dll')}]
manifest = output / 'publication.json'
manifest.write_text(json.dumps(negative), encoding='utf-8')
code, text = run(['python', ROOT / 'tools/check-publication.py', manifest, '--sample', ROOT / 'samples/dotnet', '--experimental'], 'reject-thread')
report = json.loads((output / 'compatibility.json').read_text(encoding='utf-8'))
assert code != 0 and any('Thread::' in item.get('member', '') for item in report['unsupported']), text
results.append('unsupported-thread-rejected-even-experimental')
pending = output / 'pending-project'
shutil.copytree(ROOT / 'samples/dotnet', pending, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.godot', 'bin', 'obj', 'addons', '.nuget'))
with (pending / 'Player.cs').open('a', encoding='utf-8') as file:
    file.write('\n// Deliberately unvalidated source fingerprint.\n')
manifest.write_text(json.dumps(publication), encoding='utf-8')
code, text = run(['python', ROOT / 'tools/check-publication.py', manifest, '--sample', pending], 'reject-pending')
assert code != 0, text
code, text = run(['python', ROOT / 'tools/check-publication.py', manifest, '--sample', pending, '--experimental'], 'explicit-pending')
assert code == 0 and 'experimental-pending' in text, text
results += ['pending-profile-rejected', 'explicit-pending-clearly-labelled']

project = output / 'export-project'
shutil.copytree(ROOT / 'build/m1/export-project-dotnet', project, dirs_exist_ok=True)
template = ROOT / 'build/sdk/templates/win64/interpreter/godot.windows.template_release.x86_64.leanclr_m1.mono.exe'
(project / 'export_presets.cfg').write_text(f'''[preset.0]
name="Guard"
platform="Windows Desktop"
export_filter="all_resources"
[preset.0.options]
custom_template/debug="{template.as_posix()}"
custom_template/release="{template.as_posix()}"
binary_format/architecture="x86_64"
''', encoding='utf-8')
original = ROOT / 'build/m1/payload-native-dotnet'
helper = ROOT / 'extern/godot/bin/godot.windows.editor.x86_64.leanclr_m0.mono.console.exe'
for name, mutation in [('pointer-width', None), ('runtime-version', None), ('corelib-hash', 'System.Private.CoreLib'),
                       ('bindings-hash', 'GodotSharp'), ('gameplay-integrity', None), ('aot-assembly-hash', 'DemoLogic')]:
    if name == 'aot-assembly-hash' and not args.aot_template:
        continue
    payload = output / ('payload-' + name)
    shutil.copytree(original, payload, dirs_exist_ok=True)
    contract = json.loads((payload / 'manifest.json').read_text(encoding='utf-8'))
    if name == 'pointer-width':
        contract['pointer_bits'] = 32
    elif name == 'runtime-version':
        contract['leanclr_commit'] = '0' * 40
    elif mutation:
        file = payload / (mutation + '.dll.bytes')
        data = bytearray(file.read_bytes())
        data[-1] ^= 1
        file.write_bytes(data)
        for entry in contract['files']:
            if entry['source'] == file.name:
                entry['sha256'] = hashlib.sha256(data).hexdigest()
    (payload / 'manifest.json').write_text(json.dumps(contract), encoding='utf-8')
    pack = output / (name + '.pck')
    code, text = run([helper, '--headless', '--path', project, '--export-pack', 'Guard', pack], 'export-' + name,
                     dict(os.environ, GODOT_LEANCLR_M0_STAGE=str(payload)))
    assert code == 0 and 'LEANCLR_EXPORT_PAYLOAD_OK' in text, text[-2500:]
    if name == 'gameplay-integrity':
        data = bytearray(pack.read_bytes())
        assembly = (payload / 'Gameplay.dll.bytes').read_bytes()
        assert data.count(assembly) == 1
        offset = data.index(assembly)
        data[offset + len(assembly) - 1] ^= 1
        pack.write_bytes(data)
    executable = output / (name + '.exe')
    shutil.copyfile(args.aot_template if name == 'aot-assembly-hash' else template, executable)
    code, text = run([executable, '--headless', '--', '--m0-smoke'], 'runtime-' + name)
    assert code != 0 and 'NODE2D_SMOKE_OK' not in text, text[-2500:]
    assert ('LEANCLR_PUBLICATION_REJECTED' in text or 'LEANCLR_GODOT_START_FAILED' in text or 'LEANCLR_GODOT_FATAL' in text), text[-2500:]
    results.append(name + '-rejected-before-gameplay')
(output / 'report.json').write_text(json.dumps({'status': 'passed', 'checks': results}, indent=2) + '\n', encoding='utf-8')
print('PUBLICATION_GUARDS_OK', len(results))

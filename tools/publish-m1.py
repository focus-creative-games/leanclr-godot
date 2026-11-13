"""Publish the Windows Node2D vertical sample through the isolated Godot exporter."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--helper', type=Path, default=ROOT / 'extern/godot/bin/godot.windows.editor.x86_64.leanclr_m0.mono.console.exe')
parser.add_argument('--template', type=Path, default=ROOT / 'extern/godot/bin/godot.windows.template_release.x86_64.leanclr_m1.mono.exe')
parser.add_argument('--sample', type=Path, default=ROOT / 'samples/dotnet')
parser.add_argument('--output', type=Path, default=ROOT / 'build/export/m1/windows')
args = parser.parse_args()
sample = args.sample.resolve()
build = ROOT / 'build/m1'
stage = build / ('export-project-' + sample.name)
payload = build / ('payload-' + sample.name)
output = args.output.resolve()
for directory in (stage, payload, output):
    directory.mkdir(parents=True, exist_ok=True)
lock = json.loads((ROOT / 'dependencies.json').read_text())
protected = [*sample.glob('*.cs'), *sample.glob('*.tscn'), *sample.glob('*.tres'), sample / 'project.godot', sample / 'Gameplay.csproj']
before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
for pattern in ('*.cs', '*.uid', '*.tscn', '*.tres', '*.csproj', '*.sln', 'project.godot', 'NuGet.Config'):
    for source in sample.glob(pattern):
        shutil.copyfile(source, stage / source.name)
for pattern in ('*.cs', '*.uid', '*.tscn', '*.tres', '*.csproj', '*.sln'):
    for old in stage.glob(pattern):
        if not (sample / old.name).is_file():
            old.unlink()
shutil.copytree(sample / '.godot/mono', stage / '.godot/mono', dirs_exist_ok=True)
roots = [build / f'managed/{project}/bin/Release/net10.0/{name}.dll' for project, name in
         [('Bootstrap', 'LeanClr.Bootstrap'), ('Gameplay', 'Gameplay'), ('GodotSharp', 'GodotSharp')]]
closure = json.loads(subprocess.check_output(['dotnet', str(ROOT / 'tools/managed-info/bin/Release/net10.0/ManagedInfo.dll'),
    'C:/Program Files/dotnet/shared/Microsoft.NETCore.App/10.0.8', *map(str, roots)], text=True))
corelib = next(item for item in closure if item['name'] == 'System.Private.CoreLib')
if corelib['sha256'] != lock['corelib']['native_sha256']:
    raise RuntimeError('Unverified CoreLib')
manifest = {'phase': 'M1-windows-demo', 'runtime_ready': True, 'target': 'native', 'godot_commit': lock['godot']['commit'],
            'leanclr_commit': lock['leanclr']['commit'], 'profile': 'node2d-windows-m1', 'files': []}
for item in closure:
    name = item['name'] + '.dll.bytes'
    shutil.copyfile(item['path'], payload / name)
    manifest['files'].append({'path': 'res://.leanclr/' + name, 'source': name, 'sha256': item['sha256']})
(payload / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
template = args.template.resolve().as_posix()
(stage / 'export_presets.cfg').write_text(f'''[preset.0]
name="LeanCLR Windows"
platform="Windows Desktop"
runnable=true
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path="{(output / 'leanclr-node2d.exe').as_posix()}"

[preset.0.options]
custom_template/debug="{template}"
custom_template/release="{template}"
binary_format/architecture="x86_64"
binary_format/embed_pck=false
dotnet/include_scripts_content=false
application/console_wrapper_icon=""
''', encoding='utf-8')
env = dict(os.environ, GODOT_LEANCLR_M0_STAGE=str(payload))
for name, options in [('import', ['--editor', '--import']),
                      ('export', ['--export-release', 'LeanCLR Windows', str(output / 'leanclr-node2d.exe')])]:
    result = subprocess.run([str(args.helper), '--headless', '--path', str(stage), *options], env=env,
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
    text = result.stdout + result.stderr
    (build / f'publish-{name}.log').write_text(text, encoding='utf-8')
    if result.returncode or name == 'export' and 'M1_EXPORT_PAYLOAD_OK target=native' not in text:
        raise RuntimeError(f'M1 {name} failed: {text[-4000:]}')
wrapper = args.template.with_name(args.template.name.replace('.exe', '.console.exe'))
shutil.copyfile(wrapper, output / 'leanclr-node2d.console.exe')
for filename in ['LICENSE.txt', 'ThirdPartyNotices.txt']:
    shutil.copyfile(Path('C:/Program Files/dotnet') / filename, output / filename)
shutil.copyfile(ROOT / 'extern/leanclr/LICENSE', output / 'LeanCLR-LICENSE.txt')
shutil.copyfile(ROOT / 'extern/godot/LICENSE.txt', output / 'Godot-LICENSE.txt')
after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
if before != after:
    raise RuntimeError('Development files changed during publishing')
(output / 'publication.json').write_text(json.dumps({'profile': 'node2d-windows-m1', 'dependencies': lock,
    'development_sources': after, 'assemblies': closure,
    'template_sha256': hashlib.sha256(args.template.read_bytes()).hexdigest()}, indent=2) + '\n', encoding='utf-8')
print('M1_WINDOWS_PUBLISHED', output)

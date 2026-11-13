"""Publish the Windows Node2D vertical sample through the isolated Godot exporter."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--helper', type=Path, default=ROOT / 'extern/godot/bin/godot.windows.editor.x86_64.leanclr_m0.mono.console.exe')
parser.add_argument('--template', type=Path)
parser.add_argument('--sample', type=Path, default=ROOT / 'samples/dotnet')
parser.add_argument('--output', type=Path)
parser.add_argument('--target', choices=['native', 'web', 'android'], default='native')
parser.add_argument('--smoke', action='store_true', help='Embed deterministic smoke arguments in the Android test APK')
parser.add_argument('--runtime-source', type=Path, default=ROOT / 'extern/leanclr')
args = parser.parse_args()
sample = args.sample.resolve()
build = ROOT / 'build/m1'
compiled = json.loads((build / 'managed-inputs.json').read_text(encoding='utf-8'))
current_inputs = [p for pattern in ['*.cs', '*.csproj', '*.tscn', '*.tres', 'project.godot'] for p in sample.glob(pattern)]
current_inputs.append(ROOT / 'managed/DemoLogic/Motion.cs')
current_sources = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in current_inputs}
if compiled['sample'] != str(sample) or compiled['sources'] != current_sources:
    raise RuntimeError('Managed publication sources changed or belong to another project. Run prepare_m1_managed.py --sample for this project first.')
stage = build / ('export-project-' + sample.name)
payload = build / ('payload-' + sample.name)
web = args.target == 'web'
android = args.target == 'android'
defaults = {'native': ('extern/godot/bin/godot.windows.template_release.x86_64.leanclr_m1.mono.exe', 'build/export/m1/windows'),
            'web': ('extern/godot/bin/godot.web.template_release.wasm32.nothreads.leanclr_m3.mono.zip', 'build/export/m3/web'),
            'android': ('build/android/leanclr-debug.apk', 'build/export/m4/android')}
args.template = args.template or ROOT / defaults[args.target][0]
output = (args.output or ROOT / defaults[args.target][1]).resolve()
payload = build / ('payload-' + args.target + '-' + sample.name)
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
project = stage / 'project.godot'
text = project.read_text(encoding='utf-8')
text = re.sub(r'(?ms)^\[editor_plugins\].*?(?=^\[|\Z)', '', text)
project.write_text(text, encoding='utf-8')
if android:
    project = stage / 'project.godot'
    text = project.read_text(encoding='utf-8')
    text = text.replace('[rendering]', '[rendering]\ntextures/vram_compression/import_etc2_astc=true')
    project.write_text(text, encoding='utf-8')
roots = [build / f'managed/{project}/bin/Release/net10.0/{name}.dll' for project, name in
         [('Bootstrap', 'LeanClr.Bootstrap'), ('Gameplay', 'Gameplay'), ('GodotSharp', 'GodotSharp')]]
roots.append(build / 'managed/DemoLogic/bin/Release/net10.0/DemoLogic.dll')
bcl = args.runtime_source / 'out/net10-runtime-win-x86/runtimes/win-x86/lib/net10.0' if web else Path('C:/Program Files/dotnet/shared/Microsoft.NETCore.App/10.0.8')
closure = json.loads(subprocess.check_output(['dotnet', str(ROOT / 'tools/managed-info/bin/Release/net10.0/ManagedInfo.dll'), str(bcl), *map(str, roots)], text=True))
corelib = next(item for item in closure if item['name'] == 'System.Private.CoreLib')
if corelib['sha256'] != lock['corelib']['wasm_sha256' if web else 'native_sha256']:
    raise RuntimeError('Unverified CoreLib')
manifest = {'phase': 'M4-android-demo' if android else 'M3-html5-demo' if web else 'M1-windows-demo', 'runtime_ready': True,
            'target': 'android' if android else 'wasm' if web else 'native', 'godot_commit': lock['godot']['commit'],
            'leanclr_commit': lock['leanclr']['commit'], 'profile': 'node2d-windows-m1', 'files': []}
manifest.update(pointer_bits=32 if web else 64, real_bits=32,
    calli_sha256=hashlib.sha256((build / 'calli/calli_bridges.json').read_bytes()).hexdigest())
for item in closure:
    name = item['name'] + '.dll.bytes'
    shutil.copyfile(item['path'], payload / name)
    manifest['files'].append({'path': 'res://.leanclr/' + name, 'source': name, 'sha256': item['sha256']})
for name, path in [('LeanCLR-LICENSE.txt', ROOT / 'extern/leanclr/LICENSE'), ('Godot-LICENSE.txt', ROOT / 'extern/godot/LICENSE.txt'), ('Godot-COPYRIGHT.txt', ROOT / 'extern/godot/COPYRIGHT.txt'),
                   ('DotNET-LICENSE.txt', Path('C:/Program Files/dotnet/LICENSE.txt')),
                   ('DotNET-ThirdPartyNotices.txt', Path('C:/Program Files/dotnet/ThirdPartyNotices.txt'))]:
    data = path.read_bytes()
    (payload / name).write_bytes(data)
    manifest['files'].append({'path': 'res://.leanclr/' + name, 'source': name, 'sha256': hashlib.sha256(data).hexdigest()})
(payload / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
template = args.template.resolve().as_posix()
preset_name = 'LeanCLR Android' if android else 'LeanCLR Web' if web else 'LeanCLR Windows'
platform = 'Android' if android else 'Web' if web else 'Windows Desktop'
artifact = output / ('demo.apk' if android else 'index.html' if web else 'leanclr-node2d.exe')
(stage / 'export_presets.cfg').write_text(f'''[preset.0]
name="{preset_name}"
platform="{platform}"
runnable=true
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path="{artifact.as_posix()}"

[preset.0.options]
custom_template/debug="{template}"
custom_template/release="{template}"
binary_format/architecture="x86_64"
binary_format/embed_pck=false
dotnet/include_scripts_content=false
application/console_wrapper_icon=""
variant/thread_support=false
variant/extensions_support=false
html/export_icon=false
progressive_web_app/enabled=false
''', encoding='utf-8')
if android:
    with (stage / 'export_presets.cfg').open('a', encoding='utf-8') as config:
        config.write(f'''gradle_build/use_gradle_build=false
architectures/armeabi-v7a=false
architectures/arm64-v8a=false
architectures/x86=false
architectures/x86_64=true
package/unique_name="com.focuscreative.leanclrgodot.{sample.name.lower()}"
package/name="LeanCLR {sample.name}"
version/code=1
version/name="1.0"
keystore/debug="{(ROOT / 'extern/godot/bin/editor_data/keystores/debug.keystore').as_posix()}"
keystore/debug_user="androiddebugkey"
keystore/debug_password="android"
command_line/extra_args="{'-- --m0-smoke' if args.smoke else ''}"
''')
env = dict(os.environ, GODOT_LEANCLR_M0_STAGE=str(payload))
for name, options in [('import', ['--editor', '--import']),
                      ('export', ['--export-debug' if android else '--export-release', preset_name, str(artifact)])]:
    result = subprocess.run([str(args.helper), '--headless', '--path', str(stage), *options], env=env,
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
    text = result.stdout + result.stderr
    (build / f'publish-{name}.log').write_text(text, encoding='utf-8')
    marker = 'LEANCLR_EXPORT_PAYLOAD_OK target=' + ('android' if android else 'wasm' if web else 'native')
    if result.returncode or name == 'export' and marker not in text:
        raise RuntimeError(f'M1 {name} failed: {text[-4000:]}')
if args.target == 'native':
    wrapper = args.template.with_name(args.template.name.replace('.exe', '.console.exe'))
    shutil.copyfile(wrapper, output / 'leanclr-node2d.console.exe')
elif web:
    html = artifact.read_text(encoding='utf-8')
    anchor = 'const engine = new Engine(GODOT_CONFIG);'
    if html.count(anchor) != 1:
        raise RuntimeError('Unexpected HTML shell')
    html = html.replace(anchor, "if (new URLSearchParams(location.search).has('smoke')) GODOT_CONFIG.args.push('--audio-driver', 'Dummy', '--', '--m0-smoke');\n" + anchor)
    artifact.write_text(html, encoding='utf-8')
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
print('LEANCLR_PUBLISHED', args.target, output)

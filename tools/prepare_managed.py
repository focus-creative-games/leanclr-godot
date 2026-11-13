"""Compile the sample and stage separate native/wasm BCLs, without layout patches."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runtime-source', type=Path, default=ROOT / 'extern/leanclr')
parser.add_argument('--native-runtime', type=Path, default=Path('C:/Program Files/dotnet/shared/Microsoft.NETCore.App/10.0.8'))
parser.add_argument('--wasm-runtime', type=Path)
parser.add_argument('--target', choices=['native', 'wasm', 'all'], default='all')
args = parser.parse_args()
if not (args.runtime_source / 'src/runtime/CMakeLists.txt').is_file():
    parser.error('LeanCLR sources are missing. Run git submodule update --init --recursive, or pass --runtime-source with another checkout.')
lock = json.loads((ROOT / 'dependencies.json').read_text(encoding='utf-8'))
wasm = args.wasm_runtime or args.runtime_source / 'out/net10-runtime-win-x86/runtimes/win-x86/lib/net10.0'
sdk_line = next(line for line in reversed(subprocess.check_output(['dotnet', '--list-sdks'], text=True).splitlines()) if line.startswith('10.'))
version, directory = sdk_line.split(' [', 1)
compiler = Path(directory.rstrip(']')) / version / 'Roslyn/bincore/csc.dll'
build = ROOT / 'build/managed'
build.mkdir(parents=True, exist_ok=True)
dll = build / 'Demo.Managed.dll'
subprocess.run(['dotnet', str(compiler), '/nologo', '/noconfig', '/nostdlib+', '/target:library', '/unsafe+', '/optimize+',
                f'/r:{args.native_runtime / "System.Private.CoreLib.dll"}', f'/out:{dll}', str(ROOT / 'managed/Entry.cs')], check=True)
for target, runtime in [('native', args.native_runtime), ('wasm', wasm)]:
    if args.target != 'all' and target != args.target:
        continue
    stage = ROOT / 'demo/managed' / target
    stage.mkdir(parents=True, exist_ok=True)
    manifest = {'profile': 'CORECLR_NET10', 'target': target, 'runtime': str(runtime), 'files': {}}
    for source in [dll, runtime / 'System.Private.CoreLib.dll', runtime / 'System.Runtime.dll']:
        data = source.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if source.name == 'System.Private.CoreLib.dll' and digest != lock['corelib'][target + '_sha256']:
            raise RuntimeError(f'Unverified {target} CoreLib: {digest}. Use the pinned target-specific BCL.')
        (stage / (source.name + '.bytes')).write_bytes(data)
        manifest['files'][source.name] = digest
    (stage / 'provenance.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('Staged', target, manifest['files']['System.Private.CoreLib.dll'])
notices = ROOT / 'demo/managed/notices'
notices.mkdir(parents=True, exist_ok=True)
for name in ['LICENSE.txt', 'ThirdPartyNotices.txt']:
    source = next((p / name for p in [args.native_runtime, *args.native_runtime.parents] if (p / name).is_file()), None)
    if source is None:
        raise RuntimeError(f'Missing .NET notice {name}')
    shutil.copyfile(source, notices / name)
shutil.copyfile(args.runtime_source / 'LICENSE', notices / 'LeanCLR-LICENSE.txt')
shutil.copyfile(ROOT / 'extern/godot-cpp/LICENSE.md', notices / 'GodotCPP-LICENSE.md')
shutil.copyfile(ROOT / 'THIRD_PARTY_NOTICES.md', notices / 'LeanCLR-Godot-NOTICES.md')

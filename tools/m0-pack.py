"""Probe PCK payload identity. Does not export or run a LeanCLR C# game."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--godot', type=Path, default=ROOT.parent / 'v4.7.2-stable_win64/Godot_v4.7.2-stable_win64_console.exe')
parser.add_argument('--runtime-source', type=Path, default=ROOT / 'extern/leanclr')
args = parser.parse_args()
lock = json.loads((ROOT / 'dependencies.json').read_text(encoding='utf-8'))
for target in ('native', 'wasm'):
    stage = ROOT / 'build/m0/pack' / target
    stage.mkdir(parents=True, exist_ok=True)
    bcl = (Path('C:/Program Files/dotnet/shared/Microsoft.NETCore.App/10.0.8') if target == 'native' else
           args.runtime_source / 'out/net10-runtime-win-x86/runtimes/win-x86/lib/net10.0')
    payloads = {
        'res://Player.cs': b'\n',
        'res://Main.tscn': (ROOT / 'samples/dotnet/Main.tscn').read_bytes(),
        'res://.leanclr/Gameplay.dll.bytes': (ROOT / 'samples/dotnet/.godot/mono/temp/bin/Debug/Gameplay.dll').read_bytes(),
        'res://.leanclr/System.Private.CoreLib.dll.bytes': (bcl / 'System.Private.CoreLib.dll').read_bytes(),
    }
    corelib = hashlib.sha256(payloads['res://.leanclr/System.Private.CoreLib.dll.bytes']).hexdigest()
    if corelib != lock['corelib'][target + '_sha256']:
        raise RuntimeError(f'{target}: unexpected CoreLib')
    manifest = {'phase': 'M0-container-probe', 'runtime_ready': False, 'target': target,
                'leanclr_commit': lock['leanclr']['commit'], 'files': []}
    for index, (path, data) in enumerate(payloads.items()):
        source = f'{index}.bytes'
        (stage / source).write_bytes(data)
        manifest['files'].append({'path': path, 'source': source, 'sha256': hashlib.sha256(data).hexdigest()})
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    pack = stage / 'probe.pck'
    for mode in ('pack', 'verify'):
        command = [str(args.godot.resolve()), '--headless', '--path', str(ROOT / 'build/m0'),
                   '--script', str(ROOT / 'tests/m0/pack_probe.gd'), '--', str(stage), str(pack), mode]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        (stage / f'{mode}.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        print(result.stdout, end='')
        if result.returncode or f'M0_PCK_OK mode={mode}' not in result.stdout:
            raise RuntimeError(result.stderr)

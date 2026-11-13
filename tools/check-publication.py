"""Reject known unsupported application dependencies and report the complete assembly census.

This is a conservative metadata census, not a reachability or reflection proof.
Unknown applications require explicit experimental publication until a differential
test profile is registered for their exact sources.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('publication', type=Path)
parser.add_argument('--sample', type=Path, required=True)
parser.add_argument('--experimental', action='store_true')
args = parser.parse_args()
manifest = json.loads(args.publication.read_text(encoding='utf-8-sig'))
inspector = ROOT / 'tools/managed-info/bin/Release/net10.0/ManagedInfo.dll'
census = json.loads(subprocess.check_output(['dotnet', str(inspector), '--scan',
    *[item['path'] for item in manifest['assemblies']]], text=True, encoding='utf-8'))
application = [item for item in census if item['assembly'] in ['Gameplay', 'DemoLogic']]
blocked = []
for item in application:
    for member in item['members']:
        if any(member.startswith(prefix) for prefix in ['System.Threading.Thread::', 'System.Threading.ThreadPool::',
                'System.Threading.Tasks.Task::Run', 'System.Reflection.Emit.', 'System.Runtime.Loader.',
                'System.Runtime.InteropServices.NativeLibrary::Load', 'System.Runtime.InteropServices.NativeLibrary::TryLoad',
                'System.Runtime.InteropServices.NativeLibrary::GetExport', 'System.Runtime.InteropServices.NativeLibrary::TryGetExport',
                'System.Runtime.InteropServices.NativeLibrary::Free', 'System.Reflection.Assembly::Load']):
            blocked.append({'assembly': item['assembly'], 'member': member})
    for imported in item['imports']:
        blocked.append({'assembly': item['assembly'], 'native_import': imported})
    if manifest.get('template_contract', {}).get('target') == 'html5':
        for member in item['members']:
            if member.startswith('System.Diagnostics.Stopwatch::'):
                blocked.append({'assembly': item['assembly'], 'member': member, 'reason': 'Portable runtime lacks QueryPerformanceFrequency; use Godot.Time.GetTicksUsec.'})
source_hashes = {}
for pattern in ['*.cs', '*.csproj', '*.tscn', '*.tres', 'project.godot']:
    for path in args.sample.glob(pattern):
        text = path.read_text(encoding='utf-8-sig')
        data = text.encode('utf-8')
        if path.name == 'project.godot':
            text = text.replace('[editor_plugins]\nenabled=PackedStringArray("res://addons/leanclr_publish/plugin.cfg")', '')
            data = (text.strip() + '\n').encode('utf-8')
        source_hashes[path.name] = hashlib.sha256(data).hexdigest()
source_hashes['@DemoLogic/Motion.cs'] = hashlib.sha256((ROOT / 'managed/DemoLogic/Motion.cs').read_text(encoding='utf-8-sig').encode('utf-8')).hexdigest()
profiles_path = ROOT / 'sdk/validated-profiles.json'
profiles = json.loads(profiles_path.read_text(encoding='utf-8')) if profiles_path.exists() else {}
validated = profiles.get(args.sample.name) == source_hashes
report = {'status': 'blocked' if blocked else 'validated-fixture' if validated else 'experimental-pending',
          'source_normalization': 'UTF-8 text without BOM, universal newlines; optional publisher menu section excluded.',
          'unsupported': blocked, 'sources': source_hashes, 'census': census,
          'limits': 'All closure members are inventoried; system implementation references are not claimed supported. Reflection strings, indirect delegates and dynamic inputs require execution tests.'}
(args.publication.parent / 'compatibility.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
if blocked or not validated and not args.experimental:
    raise SystemExit('Publication rejected: inspect compatibility.json; pending applications need --experimental and independent execution tests.')
print('COMPATIBILITY_OK', report['status'])

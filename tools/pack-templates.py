"""Produce a verified template bundle for the repository's publication SDK."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--mode', choices=['interpreter', 'mixed'], default='interpreter')
args = parser.parse_args()
output = ROOT / 'build/sdk/dist' / ('leanclr-godot-4.7.2-' + args.mode + '.zip')
output.parent.mkdir(parents=True, exist_ok=True)
temporary = output.with_suffix('.partial')
entries = {}
for target in ['win64', 'html5', 'android']:
    directory = ROOT / 'build/sdk/templates' / target / args.mode
    manifest = json.loads((directory / 'template.json').read_text(encoding='utf-8'))
    for name, digest in manifest['files'].items():
        path = directory / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Corrupted template: ' + str(path))
        entries[str(path.relative_to(ROOT / 'build/sdk')).replace('\\', '/')] = path
    entries[str((directory / 'template.json').relative_to(ROOT / 'build/sdk')).replace('\\', '/')] = directory / 'template.json'
for name, path in [('LeanCLR-LICENSE.txt', ROOT / 'extern/leanclr/LICENSE'), ('Godot-LICENSE.txt', ROOT / 'extern/godot/LICENSE.txt'),
                   ('Godot-COPYRIGHT.txt', ROOT / 'extern/godot/COPYRIGHT.txt'), ('DotNET-LICENSE.txt', Path('C:/Program Files/dotnet/LICENSE.txt')),
                   ('DotNET-ThirdPartyNotices.txt', Path('C:/Program Files/dotnet/ThirdPartyNotices.txt'))]:
    entries['licenses/' + name] = path
digests = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in entries.items()}
with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for name, path in entries.items():
        archive.write(path, name)
    archive.writestr('bundle.json', json.dumps({'schema': 1, 'files': digests}, indent=2) + '\n')
with zipfile.ZipFile(temporary) as archive:
    for name, digest in digests.items():
        assert hashlib.sha256(archive.read(name)).hexdigest() == digest
temporary.replace(output)
print('TEMPLATE_BUNDLE_OK', output, hashlib.sha256(output.read_bytes()).hexdigest())

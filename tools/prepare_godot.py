"""Prepare pinned official Godot sources for the private publishing helper."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--archive', type=Path, help='Use an already downloaded source archive')
args = parser.parse_args()
spec = json.loads((ROOT / 'dependencies.json').read_text(encoding='utf-8'))['godot']
destination = ROOT / 'extern/godot'
stamp = destination / '.leanclr-source.json'
if destination.exists():
    if not stamp.is_file() or json.loads(stamp.read_text(encoding='utf-8')) != spec:
        raise RuntimeError('Existing Godot directory is unverified; move it aside first.')
    print('Prepared Godot', spec['commit'])
    raise SystemExit(0)
archive_path = args.archive or ROOT / '.cache' / f"godot-{spec['commit']}.tar.gz"
if not archive_path.exists():
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    partial = archive_path.with_suffix('.partial')
    with urllib.request.urlopen(f"https://codeload.github.com/godotengine/godot/tar.gz/{spec['commit']}", timeout=120) as source:
        with partial.open('wb') as output:
            shutil.copyfileobj(source, output)
    partial.rename(archive_path)
with archive_path.open('rb') as source:
    if hashlib.file_digest(source, 'sha256').hexdigest() != spec['archive_sha256']:
        raise RuntimeError('Godot archive hash mismatch')
staging = destination.with_suffix('.partial')
staging.mkdir(parents=True, exist_ok=False)
with tarfile.open(archive_path, 'r:gz') as archive:
    for member in archive:
        parts = Path(member.name).parts[1:]
        if not parts or '..' in parts or not member.isfile():
            continue
        target = staging.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.extractfile(member) as source, target.open('wb') as output:
            shutil.copyfileobj(source, output)
(staging / '.leanclr-source.json').write_text(json.dumps(spec, indent=2) + '\n', encoding='utf-8')
staging.rename(destination)
print('Prepared Godot', spec['commit'], destination)

"""Fetch the pinned upstream godot-cpp snapshot; no runtime fork or patches."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
spec = json.loads((ROOT / 'dependencies.json').read_text())['godot-cpp']
destination = ROOT / 'extern/godot-cpp'
stamp = destination / '.leanclr-source.json'
if destination.exists():
    if not stamp.exists() or json.loads(stamp.read_text())['commit'] != spec['commit']:
        raise RuntimeError('Existing godot-cpp is unverified. Move it aside before preparing dependencies.')
    print('Verified source revision', spec['commit'])
else:
    url = f"https://codeload.github.com/godotengine/godot-cpp/tar.gz/{spec['commit']}"
    with urllib.request.urlopen(url, timeout=120) as source:
        data = source.read()
    if hashlib.sha256(data).hexdigest() != spec['archive_sha256']:
        raise RuntimeError('godot-cpp archive hash mismatch')
    staging = ROOT / 'extern/godot-cpp.partial'
    if staging.exists():
        raise RuntimeError('Interrupted staging directory exists; move it aside before retrying')
    staging.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive:
            parts = Path(member.name).parts[1:]
            if not parts or '..' in parts or not member.isfile():
                continue
            target = staging.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open('wb') as output:
                shutil.copyfileobj(source, output)
    (staging / '.leanclr-source.json').write_text(json.dumps(spec, indent=2) + '\n')
    staging.rename(destination)
    print('Prepared', destination)

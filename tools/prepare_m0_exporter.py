"""Apply the isolated M0 export-policy changes to the pinned Godot source."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'extern/godot'
spec = json.loads((ROOT / 'dependencies.json').read_text(encoding='utf-8'))['godot']
if json.loads((source / '.leanclr-source.json').read_text(encoding='utf-8')) != spec:
    raise RuntimeError('Prepare the pinned Godot source first.')
patches = ROOT / 'godot_patches/m0'
hashes = json.loads((patches / 'source-hashes.json').read_text(encoding='utf-8'))
actual = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in hashes}
if all(actual[name] == hashes[name]['before'] for name in hashes):
    for check in (True, False):
        command = ['git', '-c', 'core.fsmonitor=false', 'apply', '--directory=extern/godot']
        if check:
            command.append('--check')
        subprocess.run(command + [str(patches / 'export-policy.patch')], cwd=ROOT, check=True)
elif not all(actual[name] == hashes[name]['after'] for name in hashes):
    raise RuntimeError('Godot export sources have unexpected changes; refusing to overwrite them.')
for name, expected in hashes.items():
    if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected['after']:
        raise RuntimeError('Patched Godot source hash mismatch: ' + name)
shutil.copyfile(patches / 'LeanClrM0Export.cs', source / 'modules/mono/editor/GodotTools/GodotTools/Export/LeanClrM0Export.cs')
print('Prepared private M0 export policy; original installed editors remain unchanged.')

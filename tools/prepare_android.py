"""Prepare an isolated Android SDK using verified official package archives."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / '.tools/android-sdk'
EXISTING = Path('C:/Users/MSN/AppData/Local/Android/Sdk')
PACKAGES = [
    ('ndk/29.0.14206865', 'android-ndk-r29-windows.zip', 833850862, 'ab3bb30fbb9e6903666d60c55d11e78b04e07472'),
    ('platforms/android-36', 'platform-36_r02.zip', 65878410, '2c1a80dd4d9f7d0e6dd336ec603d9b5c55a6f576'),
    ('build-tools/36.1.0', 'build-tools_r36.1_windows.zip', 59366211, '95f048ae758dad90617975fe3f787f038b03338c'),
]
if not (EXISTING / 'licenses/android-sdk-license').is_file():
    raise RuntimeError('An existing accepted Android SDK license is required; this tool does not accept license agreements.')
SDK.mkdir(parents=True, exist_ok=True)
shutil.copytree(EXISTING / 'licenses', SDK / 'licenses', dirs_exist_ok=True)
shutil.copytree(EXISTING / 'platform-tools', SDK / 'platform-tools', dirs_exist_ok=True)
cache = ROOT / '.cache/android'
cache.mkdir(parents=True, exist_ok=True)


def prepare(spec):
    relative, name, size, digest = spec
    destination = SDK / relative
    stamp = destination / '.leanclr-package.json'
    expected = {'url': 'https://dl.google.com/android/repository/' + name, 'size': size, 'sha1': digest}
    if stamp.is_file() and json.loads(stamp.read_text()) == expected:
        return
    if destination.exists():
        raise RuntimeError('Unverified existing SDK package: ' + str(destination))
    archive_path = cache / name
    if not archive_path.exists():
        partial = archive_path.with_suffix('.partial')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            source = opener.open(expected['url'], timeout=60)
        except Exception:
            source = urllib.request.urlopen(expected['url'], timeout=60)
        print('Downloading', name, size, flush=True)
        with source, partial.open('wb') as output:
            shutil.copyfileobj(source, output, 1024 * 1024)
        partial.rename(archive_path)
    with archive_path.open('rb') as stream:
        if archive_path.stat().st_size != size or hashlib.file_digest(stream, 'sha1').hexdigest() != digest:
            raise RuntimeError('Android package integrity mismatch: ' + name)
    destination.mkdir(parents=True)
    with zipfile.ZipFile(archive_path) as archive:
        for entry in archive.infolist():
            parts = Path(entry.filename).parts[1:]
            if not parts or '..' in parts or entry.is_dir():
                continue
            path = destination.joinpath(*parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, path.open('wb') as output:
                shutil.copyfileobj(source, output)
    stamp.write_text(json.dumps(expected, indent=2) + '\n')
    print('Prepared', relative, flush=True)


with ThreadPoolExecutor(max_workers=3) as pool:
    list(pool.map(prepare, PACKAGES))
print('Android SDK prepared:', SDK, flush=True)

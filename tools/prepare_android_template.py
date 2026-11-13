"""Combine the official Android Java container with the LeanCLR engine library."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'build/templates/android_debug.apk'
destination = ROOT / 'build/android/leanclr-debug.apk'
libraries = ROOT / 'extern/godot/platform/android/java/lib/libs/release/x86_64'
if not source.is_file():
    raise RuntimeError('Run python tools/fetch_templates.py --android first.')
if not (libraries / 'libgodot_android.so').is_file():
    raise RuntimeError('Build the Android LeanCLR engine first.')
with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, 'w') as output:
    for entry in original.infolist():
        if entry.filename.startswith('lib/') or entry.filename.startswith('META-INF/'):
            continue
        output.writestr(entry, original.read(entry.filename))
    for name in ['libgodot_android.so', 'libc++_shared.so']:
        output.write(libraries / name, 'lib/x86_64/' + name, compress_type=zipfile.ZIP_STORED)
settings = ROOT / 'extern/godot/bin/editor_data/editor_settings-4.7.tres'
java = Path(shutil.which('java')).resolve().parent.parent
debug_key = ROOT / 'extern/godot/bin/editor_data/keystores/debug.keystore'
if not debug_key.exists():
    debug_key.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(java / 'bin/keytool.exe'), '-genkeypair', '-keystore', str(debug_key), '-storepass', 'android',
        '-alias', 'androiddebugkey', '-keypass', 'android', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '3650',
        '-dname', 'CN=Android Debug,O=Android,C=US', '-noprompt'], check=True)
values = {'export/android/android_sdk_path': (ROOT / '.tools/android-sdk').as_posix(), 'export/android/java_sdk_path': java.as_posix()}
text = settings.read_text(encoding='utf-8')
for key, value in values.items():
    line = key + ' = ' + json.dumps(value)
    pattern = '^' + re.escape(key) + r' = .*?$'
    if re.search(pattern, text, re.MULTILINE):
        text = re.sub(pattern, lambda match: line, text, flags=re.MULTILINE)
    else:
        text = text.replace('[resource]', '[resource]\n' + line)
settings.write_text(text, encoding='utf-8')
report = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'template_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
          'abi': 'x86_64', 'libraries': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in libraries.glob('*.so')}}
(ROOT / 'build/android/template.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print('Prepared Android LeanCLR template:', destination)

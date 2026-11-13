"""Fetch selected official 4.7.2 templates using byte ranges and verify ZIP CRCs."""
import argparse
from pathlib import Path
import struct
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/Godot_v4.7.2-stable_export_templates.tpz'
SIZE = 1281349702
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'build/templates')
parser.add_argument('--android', action='store_true', help='Fetch the official Android APK container instead of desktop/Web templates')
args = parser.parse_args()

def fetch(start, end):
    if args.android and end - start + 1 > 2 * 1024 * 1024:
        ranges = [(position, min(position + 2 * 1024 * 1024 - 1, end)) for position in range(start, end + 1, 2 * 1024 * 1024)]
        print('Fetching Android container in', len(ranges), 'verified byte ranges', flush=True)
        with ThreadPoolExecutor(max_workers=16) as pool:
            return b''.join(pool.map(lambda bounds: fetch(*bounds), ranges))
    cached = ROOT / '.cache/templates' / f'{start}-{end}.part'
    if args.android and cached.is_file() and cached.stat().st_size == end - start + 1:
        return cached.read_bytes()
    url = URL
    if args.android:
        url = URL + f'?leanclr_start={start}&leanclr_end={end}'
    request = urllib.request.Request(url, headers={'Range': f'bytes={start}-{end}', 'Accept': 'application/octet-stream'})
    opener = urllib.request.build_opener()
    with opener.open(request, timeout=180) as response:
        if response.status != 206:
            raise RuntimeError('Server does not support ranged downloads')
        if response.headers.get('Content-Range') != f'bytes {start}-{end}/{SIZE}':
            raise RuntimeError('Unexpected byte range response')
        data = response.read()
    if len(data) != end - start + 1:
        raise RuntimeError('Incomplete template download')
    if args.android:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
        print('Verified range', start, end, flush=True)
    return data

tail = fetch(SIZE - 65536, SIZE - 1)
eocd = struct.unpack_from('<4s4H2LH', tail, tail.rfind(b'PK\x05\x06'))
position = eocd[6] - (SIZE - len(tail))
args.output.mkdir(parents=True, exist_ok=True)
wanted = {'web_dlink_nothreads_debug.zip', 'web_dlink_nothreads_release.zip',
          'windows_release_x86_64.exe', 'windows_release_x86_64_console.exe'}
if args.android:
    wanted = {'android_debug.apk'}
while tail[position:position + 4] == b'PK\x01\x02':
    entry = struct.unpack_from('<4s6H3L5H2L', tail, position)
    name = tail[position + 46:position + 46 + entry[10]].decode()
    position += 46 + entry[10] + entry[11] + entry[12]
    filename = Path(name).name
    if filename not in wanted:
        continue
    target = args.output / filename
    if target.exists() and zlib.crc32(target.read_bytes()) == entry[7]:
        print('Verified cached', filename, flush=True)
        continue
    offset, compressed = entry[16], entry[8]
    header = fetch(offset, offset + 29)
    local = struct.unpack('<4s5H3L2H', header)
    begin = offset + 30 + local[9] + local[10]
    payload = fetch(begin, begin + compressed - 1)
    data = zlib.decompress(payload, -15) if entry[4] == 8 else payload
    if len(data) != entry[9] or zlib.crc32(data) != entry[7]:
        raise RuntimeError('Template CRC/size mismatch: ' + filename)
    partial = target.with_suffix('.partial')
    partial.write_bytes(data)
    partial.replace(target)
    print('Downloaded and verified', filename, len(data), flush=True)

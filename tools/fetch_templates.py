"""Fetch selected official 4.7.2 templates using byte ranges and verify ZIP CRCs."""
import argparse
from pathlib import Path
import struct
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/Godot_v4.7.2-stable_export_templates.tpz'
SIZE = 1281349702
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'build/templates')
args = parser.parse_args()

def fetch(start, end):
    request = urllib.request.Request(URL, headers={'Range': f'bytes={start}-{end}'})
    with urllib.request.urlopen(request, timeout=180) as response:
        if response.status != 206:
            raise RuntimeError('Server does not support ranged downloads')
        data = response.read()
    if len(data) != end - start + 1:
        raise RuntimeError('Incomplete template download')
    return data

tail = fetch(SIZE - 65536, SIZE - 1)
eocd = struct.unpack_from('<4s4H2LH', tail, tail.rfind(b'PK\x05\x06'))
position = eocd[6] - (SIZE - len(tail))
args.output.mkdir(parents=True, exist_ok=True)
wanted = {'web_dlink_nothreads_debug.zip', 'web_dlink_nothreads_release.zip',
          'windows_release_x86_64.exe', 'windows_release_x86_64_console.exe'}
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

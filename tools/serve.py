"""Preview the Web export at http://127.0.0.1:8060/."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--port', type=int, default=8060)
args = parser.parse_args()
directory = Path(__file__).resolve().parents[1] / 'build/export/web'
print(f'http://127.0.0.1:{args.port}/', flush=True)
ThreadingHTTPServer(('127.0.0.1', args.port), partial(SimpleHTTPRequestHandler, directory=str(directory))).serve_forever()

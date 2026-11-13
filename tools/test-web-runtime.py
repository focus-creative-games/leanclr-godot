"""Run the published LeanCLR template in a real Chromium WebGL browser."""
import argparse
import io
import hashlib
from functools import partial
import http.server
import json
import re
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.tools/browser'))
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory', type=Path, default=ROOT / 'build/export/m3/semantics')
parser.add_argument('--expected', default='M2_SEMANTICS_OK checks=15 observed=31')
parser.add_argument('--movement', action='store_true')
parser.add_argument('--reloads', type=int, default=2)
parser.add_argument('--report-dir', type=Path)
parser.add_argument('--label')
parser.add_argument('--require-aot', action='store_true')
args = parser.parse_args()
logs = args.report_dir or ROOT / 'build/m3'
logs.mkdir(parents=True, exist_ok=True)


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *unused):
        pass


server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(args.directory.resolve())))
threading.Thread(target=server.serve_forever, daemon=True).start()
messages, errors = [], []
label = args.label or ('movement' if args.movement else 'extended' if args.expected.startswith('M5_') else 'semantics' if args.expected.startswith('M2_') else 'node2d')
live_log = logs / f'console-{label}.log'
live_log.write_text('', encoding='utf-8')


def record_console(message):
    messages.append(message.text)
    if any(marker in message.text for marker in ['M5_FAIL', 'M2_FAIL', 'M0_DOTNET_FAIL', 'LEANCLR_GODOT_FATAL', 'LEANCLR_PUBLICATION_REJECTED']):
        errors.append(message.text)
    with live_log.open('a', encoding='utf-8') as output:
        output.write(message.text + '\n')

try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe', headless=True,
            args=['--enable-unsafe-swiftshader', '--disable-background-networking'])
        page = browser.new_page(viewport={'width': 960, 'height': 640})
        page.on('console', record_console)
        page.on('pageerror', lambda error: errors.append(str(error)))
        query = '' if args.movement else '?smoke'
        page.goto(f'http://127.0.0.1:{server.server_port}/index.html{query}', wait_until='domcontentloaded')
        deadline = time.monotonic() + 120
        expected = 'LEANCLR_GODOT_READY backend=LeanCLR' if args.movement else args.expected
        while time.monotonic() < deadline and not any(expected in line for line in messages) and not errors:
            page.wait_for_timeout(100)
        if not any(expected in line for line in messages) or errors:
            raise RuntimeError('Initial browser execution failed: ' + str(errors) + '\n' + '\n'.join(messages[-20:]))
        if not args.movement:
            for reload_index in range(args.reloads):
                page.wait_for_timeout(200)
                page.reload(wait_until='domcontentloaded')
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline and sum(args.expected in line for line in messages) < reload_index + 2 and not errors:
                    page.wait_for_timeout(100)
            if sum(args.expected in line for line in messages) != args.reloads + 1:
                raise RuntimeError('Browser reload did not create a clean new runtime instance')
        if args.movement:
            from PIL import Image
            def center(data):
                image = Image.open(io.BytesIO(data)).convert('RGB')
                points = [(index % image.width, index // image.width) for index, (red, green, blue) in enumerate(image.getdata())
                          if 70 <= red <= 150 and 100 <= green <= 190 and blue >= 190]
                if len(points) < 100:
                    raise RuntimeError('The C# blue circle was not rendered')
                return sum(x for x, _ in points) / len(points)
            page.wait_for_timeout(1200)
            canvas = page.locator('#canvas')
            canvas.click(position={'x': 15, 'y': 15})
            before = canvas.screenshot()
            start_x = center(before)
            page.keyboard.down('ArrowRight')
            page.wait_for_timeout(1000)
            page.keyboard.up('ArrowRight')
            after = canvas.screenshot()
            end_x = center(after)
            (logs / 'movement-before.png').write_bytes(before)
            (logs / 'movement-after.png').write_bytes(after)
            if end_x - start_x < 40:
                raise RuntimeError('Browser keyboard input did not move the C# Node2D')
            messages.append(f'WEB_MOVEMENT_OK from={start_x:.2f} to={end_x:.2f}')
        page.screenshot(path=str(logs / f'browser-{label}.png'))
        browser_version = browser.version
        browser.close()
finally:
    server.shutdown()
    (logs / f'browser-{label}.json').write_text(json.dumps({'messages': messages, 'errors': errors}, ensure_ascii=False, indent=2), encoding='utf-8')
for line in messages:
    print(line)
required = 'WEB_MOVEMENT_OK' if args.movement else args.expected
if errors or not any(required in line for line in messages):
    raise RuntimeError('Web runtime did not pass: ' + str(errors))
if not any('LEANCLR_GODOT_READY backend=LeanCLR' in line for line in messages):
    raise RuntimeError('LeanCLR backend did not initialize')
if args.require_aot and sum('LEANCLR_AOT_HOTCALL module=DemoLogic step=4 benchmark=0' in line for line in messages) != args.reloads + 1:
    raise RuntimeError('Compiled gameplay entry counters were not observed on every run')
memory_sizes = [int(match[1]) for line in messages if (match := re.search(r'LEANCLR_WASM_MEMORY bytes=(\d+)', line))]
if args.expected.startswith('M5_EXTENDED') and not args.movement:
    if len(memory_sizes) != args.reloads + 1 or not all(128 * 1024 * 1024 < size <= 384 * 1024 * 1024 for size in memory_sizes):
        raise RuntimeError('Wasm memory growth or retained-heap budget failed: ' + str(memory_sizes))
print('WEB_RUNTIME_OK', required)
(logs / f'validation-{label}.json').write_text(json.dumps({'status': 'passed', 'browser': browser_version,
    'runs': 1 if args.movement else args.reloads + 1, 'expected': required,
    'wasm_memory_bytes': memory_sizes,
    'files': {name: hashlib.sha256((args.directory / name).read_bytes()).hexdigest() for name in ['index.wasm', 'index.pck', 'index.js']}}, indent=2) + '\n', encoding='utf-8')

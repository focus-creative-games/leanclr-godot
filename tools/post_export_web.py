"""Enable the deterministic gameplay smoke via the local Web URL's ?smoke flag."""
from pathlib import Path

page = Path(__file__).resolve().parents[1] / 'build/export/web/index.html'
html = page.read_text(encoding='utf-8')
anchor = 'const engine = new Engine(GODOT_CONFIG);'
replacement = '''if (new URLSearchParams(window.location.search).has('smoke')) {
    GODOT_CONFIG.args.push('--', '--smoke-test');
}
const engine = new Engine(GODOT_CONFIG);'''
if html.count(anchor) != 1:
    raise RuntimeError('Unexpected official HTML shell structure')
page.write_text(html.replace(anchor, replacement), encoding='utf-8')

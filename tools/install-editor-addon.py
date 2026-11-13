"""Install the optional publish menu into a bundled SDK sample project."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('project', type=Path)
args = parser.parse_args()
project = args.project.resolve()
if project.parent != ROOT / 'samples':
    raise SystemExit('The current editor adapter supports bundled SDK samples only.')
shutil.copytree(ROOT / 'addons/leanclr_publish', project / 'addons/leanclr_publish', dirs_exist_ok=True)
config = project / 'project.godot'
text = config.read_text(encoding='utf-8')
if '[editor_plugins]' not in text:
    text += '\n[editor_plugins]\nenabled=PackedStringArray("res://addons/leanclr_publish/plugin.cfg")\n'
elif 'res://addons/leanclr_publish/plugin.cfg' not in text:
    raise SystemExit('Merge the plugin into your existing editor_plugins list explicitly.')
config.write_text(text, encoding='utf-8')
print('EDITOR_ADDON_READY', project)

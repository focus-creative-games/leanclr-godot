"""Exclude desktop CLR hosting code when building a LeanCLR publication template."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
module = ROOT / 'extern/godot/modules/mono'
path = module / 'mono_gd/gd_mono.cpp'
text = path.read_text(encoding='utf-8')
if '// LeanCLR portable hosting boundary' not in text:
    start = 'namespace {\nhostfxr_initialize_for_dotnet_command_line_fn'
    if text.count(start) != 1:
        raise RuntimeError('Unexpected Godot host namespace')
    text = text.replace(start, '// LeanCLR portable hosting boundary\n#ifndef LEANCLR_GODOT\n' + start)
    text = text.replace('} // namespace\n\nbool GDMono::should_initialize()', '} // namespace\n#endif\n\nbool GDMono::should_initialize()')
    begin = text.index('void GDMono::initialize() {')
    end = text.index('#ifdef TOOLS_ENABLED\nvoid GDMono::_try_load_project_assembly()', begin)
    body = text[begin:end]
    body = body.replace('return;\n#endif', 'return;\n#else', 1)
    closing = body.rfind('}')
    body = body[:closing] + '#endif\n' + body[closing:]
    text = text[:begin] + body + text[end:]
    path.write_text(text, encoding='utf-8', newline='\n')
config = module / 'config.py'
text = config.read_text(encoding='utf-8')
if 'LEANCLR_GODOT_RUNTIME' not in text:
    text = 'import os\n\n' + text
    text = text.replace('if "mono" not in supported:',
        'if "mono" not in supported and not (not env.editor_build and env["platform"] == "web" and os.environ.get("LEANCLR_GODOT_RUNTIME")):')
    config.write_text(text, encoding='utf-8', newline='\n')
print('Prepared portable LeanCLR hosting guards; editor .NET hosting is retained.')

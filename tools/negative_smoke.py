"""Check missing/foreign-width CoreLib rejection in isolated Godot projects."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--godot', type=Path, default=ROOT.parent / 'v4.7.2-stable_win64/Godot_v4.7.2-stable_win64_console.exe')
args = parser.parse_args()
for case in ['missing-corelib', 'foreign-corelib']:
    base = ROOT / 'build/negative'
    base.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix=case + '-', dir=base))
    for name in ['project.godot', 'main.gd', 'main.tscn']:
        shutil.copyfile(ROOT / 'demo' / name, project / name)
    shutil.copytree(ROOT / 'demo/addons', project / 'addons')
    shutil.copytree(ROOT / 'demo/managed/native', project / 'managed/native')
    corelib = project / 'managed/native/System.Private.CoreLib.dll.bytes'
    if case == 'missing-corelib':
        corelib.rename(corelib.with_suffix('.unavailable'))
    else:
        shutil.copyfile(ROOT / 'demo/managed/wasm/System.Private.CoreLib.dll.bytes', corelib)
    (project / '.godot').mkdir()
    (project / '.godot/extension_list.cfg').write_text('res://addons/leanclr/leanclr.gdextension\n')
    result = subprocess.run([str(args.godot), '--headless', '--path', str(project), '--', '--smoke-test'],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    log = result.stdout.decode(errors='replace')
    (ROOT / 'build' / f'{case}.log').write_text(log, encoding='utf-8')
    expected_files = '0/0' if case == 'missing-corelib' else '1/1'
    if (result.returncode != 1 or 'Runtime initialization failed' not in log or 'LEANCLR_READY' in log
            or f'LEANCLR_STOPPED files={expected_files}' not in log):
        raise RuntimeError(f'{case} did not reject safely: {result.returncode}\n{log}')
    if case == 'foreign-corelib' and 'pointer size 4 is incompatible with runtime pointer size 8' not in log:
        raise RuntimeError('Missing pointer-width diagnostic\n' + log)
    print(case, 'PASS (controlled startup failure)')

"""Compare object, signal, resource and lifetime contracts on .NET and LeanCLR."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--skip-build', action='store_true')
args = parser.parse_args()
sample = ROOT / 'samples/semantics'
logs = ROOT / 'build/m2'
logs.mkdir(parents=True, exist_ok=True)
godot = ROOT.parent / 'Godot_v4.7.2-stable_mono_win64/Godot_v4.7.2-stable_mono_win64_console.exe'
feed = godot.parent / 'GodotSharp/Tools/nupkgs'
(sample / 'NuGet.Config').write_text(f'<configuration><packageSources><clear/><add key="godot" value="{feed}"/></packageSources></configuration>', encoding='utf-8')


def run(command, name):
    result = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
    text = result.stdout + result.stderr
    (logs / (name + '.log')).write_text(text, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(name + ': ' + text[-3500:])
    return text


run(['dotnet', 'build', sample / 'Gameplay.csproj', '-c', 'Debug', '--nologo'], 'dotnet-build')
run([godot, '--headless', '--path', sample, '--editor', '--import'], 'import')
official = run([godot, '--headless', '--path', sample, '--quit-after', '30'], 'dotnet-run')
if not args.skip_build:
    run([shutil.which('pwsh') or 'powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ROOT / 'tools/build-m1.ps1', '-Sample', sample], 'build')
    run(['python', ROOT / 'tools/publish-m1.py', '--sample', sample, '--output', ROOT / 'build/export/m2/windows'], 'publish')
expected = re.findall(r'^M2_PASS (.+)$', official, re.MULTILINE)
if len(expected) != 15 or 'M2_SEMANTICS_OK checks=15 observed=31' not in official:
    raise RuntimeError('Official contract baseline incomplete')
executable = ROOT / 'build/export/m2/windows/leanclr-node2d.console.exe'
for index in range(3):
    actual = run([executable, '--headless', '--verbose', '--quit-after', '30'], f'leanclr-run-{index}')
    if re.findall(r'^M2_PASS (.+)$', actual, re.MULTILINE) != expected or 'M2_SEMANTICS_OK checks=15 observed=31' not in actual:
        raise RuntimeError('Semantic difference against official .NET')
    if re.search(r'leaked at exit|resources still in use|unclaimed string names|M2_FAIL|LEANCLR_GODOT_FATAL', actual, re.IGNORECASE):
        raise RuntimeError('Lifetime or runtime failure detected')
(logs / 'validation.json').write_text(json.dumps({'status': 'passed', 'platform': 'windows-x64', 'checks': expected,
    'fresh_process_runs': 3, 'iterations_per_process': 32, 'resource_leaks': 0}, indent=2) + '\n', encoding='utf-8')
print('M2_ALL_OK contracts=15 fresh_process_runs=3 resource_leaks=0')

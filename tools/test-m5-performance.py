"""Compare deterministic .NET, LeanCLR interpreter and real gameplay AOT execution."""
import argparse
import json
from pathlib import Path
import re
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runs', type=int, default=7)
args = parser.parse_args()
logs = ROOT / 'build/m5/performance'
logs.mkdir(parents=True, exist_ok=True)
official = ROOT.parent / 'Godot_v4.7.2-stable_mono_win64/Godot_v4.7.2-stable_mono_win64_console.exe'
commands = {'dotnet': [official, '--path', ROOT / 'samples/dotnet'],
            'interpreter': [ROOT / 'build/export/m5/interpreter/leanclr-node2d.console.exe'],
            'aot': [ROOT / 'build/export/m5/aot/leanclr-node2d.console.exe']}
results = {}
for mode, command in commands.items():
    runs = []
    for index in range(args.runs):
        start = time.monotonic()
        result = subprocess.run(list(map(str, command)) + ['--headless', '--max-fps', '10', '--', '--m0-smoke', '--benchmark'],
                                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        text = result.stdout + result.stderr
        (logs / f'{mode}-{index}.log').write_text(text, encoding='utf-8')
        match = re.search(r'M5_BENCH ticks=(\d+) frequency=(\d+) checksum=(-?\d+) managed_bytes=(\d+)', text)
        assert result.returncode == 0 and match and 'frames=4 x=8 speed=120' in text, text[-2500:]
        assert int(match[3]) == 1834275088, text
        if mode == 'aot':
            assert 'LEANCLR_AOT_EXECUTED module=DemoLogic step=4 benchmark=2' in text, text
        if mode == 'interpreter':
            assert 'LEANCLR_AOT_EXECUTED' not in text, text
        runs.append({'compute_ms': int(match[1]) * 1000 / int(match[2]),
                     'process_ms': (time.monotonic() - start) * 1000, 'managed_bytes': int(match[4])})
    results[mode] = {'runs': runs, 'median_compute_ms': statistics.median(r['compute_ms'] for r in runs),
                     'max_compute_ms': max(r['compute_ms'] for r in runs)}
speedup = results['interpreter']['median_compute_ms'] / results['aot']['median_compute_ms']
# This is a bounded integer-compute contract, not a renderer FPS claim.
assert speedup >= 2, speedup
assert results['aot']['max_compute_ms'] < 20
assert results['interpreter']['max_compute_ms'] < 2000
report = {'status': 'passed', 'iterations': 200000, 'warmup_iterations': 10000, 'results': results,
          'aot_speedup_vs_interpreter': speedup, 'budgets': {'minimum_aot_speedup': 2, 'aot_max_ms': 20, 'interpreter_max_ms': 2000},
          'limits': 'Headless CPU microbenchmark; process_ms includes four frames at max-fps 10. No claim about frame percentiles, GPU time or full-game performance.'}
(logs / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print('M5_PERFORMANCE_OK speedup=', round(speedup, 2))

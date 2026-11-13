"""Compare deterministic .NET, LeanCLR interpreter and real gameplay AOT execution."""
import argparse
import ctypes
import json
from pathlib import Path
import re
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runs', type=int, default=7)
parser.add_argument('--interpreter', type=Path, default=ROOT / 'build/export/m5/interpreter/leanclr-node2d.exe')
parser.add_argument('--aot', type=Path, default=ROOT / 'build/export/m5/aot/leanclr-node2d.exe')
args = parser.parse_args()
logs = ROOT / 'build/m5/performance'
logs.mkdir(parents=True, exist_ok=True)
official = ROOT.parent / 'Godot_v4.7.2-stable_mono_win64/Godot_v4.7.2-stable_mono_win64.exe'
commands = {'dotnet': [official, '--path', ROOT / 'samples/dotnet'],
            'interpreter': [args.interpreter], 'aot': [args.aot]}
results = {}
float_baseline = None


class MemoryCounters(ctypes.Structure):
    _fields_ = [('size', ctypes.c_ulong), ('faults', ctypes.c_ulong),
                ('peak_working_set', ctypes.c_size_t), ('working_set', ctypes.c_size_t),
                ('peak_paged_pool', ctypes.c_size_t), ('paged_pool', ctypes.c_size_t),
                ('peak_nonpaged_pool', ctypes.c_size_t), ('nonpaged_pool', ctypes.c_size_t),
                ('pagefile', ctypes.c_size_t), ('peak_pagefile', ctypes.c_size_t)]


def execute(command):
    with tempfile.TemporaryFile() as capture:
        process = subprocess.Popen(list(map(str, command)), stdout=capture, stderr=subprocess.STDOUT)
        start = time.monotonic()
        peak = 0
        timeout = False
        while process.poll() is None:
            counters = MemoryCounters()
            counters.size = ctypes.sizeof(counters)
            if ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(int(process._handle)), ctypes.byref(counters), counters.size):
                peak = max(peak, counters.peak_working_set)
            if time.monotonic() - start > 30:
                process.kill()
                timeout = True
                break
            time.sleep(.005)
        process.wait(timeout=5)
        capture.seek(0)
        text = capture.read().decode('utf-8', errors='replace')
        if timeout:
            raise RuntimeError('Performance process timed out: ' + text[-3500:])
        return process.returncode, text, peak


for mode, command in commands.items():
    runs = []
    for index in range(args.runs):
        start = time.monotonic()
        code, text, peak = execute([*command, '--headless', '--max-fps', '10', '--', '--m0-smoke', '--benchmark'])
        (logs / f'{mode}-{index}.log').write_text(text, encoding='utf-8')
        match = re.search(r'M5_BENCH ticks=(\d+) frequency=(\d+) checksum=(-?\d+) managed_bytes=(\d+)', text)
        assert code == 0 and match and 'frames=4 x=8 speed=120' in text, text[-2500:]
        assert int(match[3]) == 1834275088, text
        float_bits = int(re.search(r'M5_FLOAT bits=(-?\d+)', text)[1])
        if float_baseline is None:
            float_baseline = float_bits
        assert float_bits == float_baseline, text
        if mode == 'aot':
            assert 'LEANCLR_AOT_EXECUTED module=DemoLogic step=104 benchmark=2' in text, text
        if mode == 'interpreter':
            assert 'LEANCLR_AOT_EXECUTED' not in text, text
        runs.append({'compute_ms': int(match[1]) * 1000 / int(match[2]),
                     'process_ms': (time.monotonic() - start) * 1000, 'managed_bytes': int(match[4]), 'peak_working_set': peak})
    results[mode] = {'runs': runs, 'median_compute_ms': statistics.median(r['compute_ms'] for r in runs),
                     'max_compute_ms': max(r['compute_ms'] for r in runs)}
    profiles = []
    for index in range(3):
        code, text, peak = execute([*command, '--headless', '--max-fps', '1000', '--', '--profile'])
        (logs / f'{mode}-profile-{index}.log').write_text(text, encoding='utf-8')
        match = re.search(r'M5_PROFILE samples=232 p50_ticks=(\d+) p95_ticks=(\d+) max_ticks=(\d+) gc_ticks=(\d+) allocated_bytes=(\d+) frequency=(\d+)', text)
        assert code == 0 and match and 'frames=240 x=480 speed=120' in text, text[-2500:]
        if mode == 'aot':
            assert 'LEANCLR_AOT_EXECUTED module=DemoLogic step=240 benchmark=0' in text
        scale = 1000 / int(match[6])
        profiles.append({'p50_cpu_ms': int(match[1]) * scale, 'p95_cpu_ms': int(match[2]) * scale,
            'max_cpu_ms': int(match[3]) * scale, 'gc_pause_ms': int(match[4]) * scale,
            'allocated_bytes_per_frame': int(match[5]) / 232, 'peak_working_set': peak})
    results[mode]['frame_profiles'] = profiles
    if mode != 'dotnet':
        assert all(p['p95_cpu_ms'] < 2 and p['gc_pause_ms'] < 20 and p['allocated_bytes_per_frame'] < 64 and
                   0 < p['peak_working_set'] < 256 * 1024 * 1024 for p in profiles), profiles
speedup = results['interpreter']['median_compute_ms'] / results['aot']['median_compute_ms']
# This is a bounded integer-compute contract, not a renderer FPS claim.
assert speedup >= 2, speedup
assert results['aot']['max_compute_ms'] < 20
assert results['interpreter']['max_compute_ms'] < 2000
report = {'status': 'passed', 'iterations': 200000, 'warmup_iterations': 10000, 'float_result_bits': float_baseline, 'results': results,
          'aot_speedup_vs_interpreter': speedup, 'budgets': {'minimum_aot_speedup': 2, 'aot_max_ms': 20, 'interpreter_max_ms': 2000,
          'frame_p95_cpu_ms': 2, 'gc_pause_ms': 20, 'managed_bytes_per_frame': 64, 'peak_working_set_mib': 256},
          'limits': 'Headless CPU workloads on this Windows machine. Frame profiles time C# Input/Position/QueueRedraw work, excluding the first 8 frames and GPU drawing. Process timings include the frame cap. These are fixture regression budgets, not whole-game performance promises.'}
(logs / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print('M5_PERFORMANCE_OK speedup=', round(speedup, 2))

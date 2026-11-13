"""Generate and instrument the bounded DemoLogic AOT module, preserving IL fallback elsewhere."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runtime-source', type=Path, default=ROOT / 'extern/leanclr')
args = parser.parse_args()
source = args.runtime_source.resolve()
output = ROOT / 'build/m5/aot'
assembly = ROOT / 'build/m1/managed/DemoLogic/bin/Release/net10.0/DemoLogic.dll'
subprocess.run(['dotnet', str(source / 'out/dotnet/LeanAOT/Release/net8.0/LeanAOT.dll'),
    '--leanaot-runtime-api-profile', 'coreclr-net10', '-d', str(assembly.parent),
    '-d', 'C:/Program Files/dotnet/shared/Microsoft.NETCore.App/10.0.8',
    '-a', 'DemoLogic', '-o', str(output)], check=True)
body = output / 'DemoLogic.method_body_part1.cpp'
text = body.read_text(encoding='utf-8')
# Counters are diagnostics at entry only, outside the benchmark loop. The single
# runtime owner thread is enforced by the host, so these require no atomics.
text = '#include <cstdio>\nstatic unsigned long long step_calls = 0, benchmark_calls = 0;\n' + text
for method, counter in [('Step', 'step_calls'), ('Benchmark', 'benchmark_calls')]:
    pattern = r'(leanclr::RtResult<[^\n]+_Motion_' + method + r'_[^\n]+\n\{)'
    text, count = re.subn(pattern, r'\1\n ++' + counter + ';', text)
    assert count == 1, method
text += '''
extern "C" void leanclr_godot_aot_report() {
 std::fprintf(stderr, "LEANCLR_AOT_EXECUTED module=DemoLogic step=%llu benchmark=%llu\\n", step_calls, benchmark_calls);
}
'''
body.write_text(text, encoding='utf-8')
files = [*output.glob('*.cpp'), *output.glob('*.h')]
subprocess.run([str(source / 'tools/clang-format/clang-format.exe'), '-i',
                '--style=file:' + str(source / '.clang-format'), *map(str, files)], check=True)
report = {'mode': 'mixed', 'aot_assembly_sha256': hashlib.sha256(assembly.read_bytes()).hexdigest(),
          'aot_methods': ['DemoLogic.Motion.Step', 'DemoLogic.Motion.Benchmark'],
          'interpreted': ['Gameplay', 'GodotSharp', 'LeanClr.Bootstrap', 'BCL'],
          'retention': 'Keep complete IL and metadata for every assembly in the resolved reference closure; no member stripping.',
          'generated_sources': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
(output.parent / 'aot-manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')

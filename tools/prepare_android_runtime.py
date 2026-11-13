"""Stage the runtime with narrowly scoped Android POSIX portability repairs."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=ROOT / 'extern/leanclr')
args = parser.parse_args()
destination = ROOT / 'build/android/leanclr-source'
shutil.copytree(args.source / 'src/runtime', destination / 'src/runtime', dirs_exist_ok=True)
shutil.copyfile(args.source / '.clang-format', destination / '.clang-format')
changes = {
    'vm/calli_native.cpp': (
        '#if (defined(_WIN32) && defined(_M_X64)) || (defined(__EMSCRIPTEN__) && UINTPTR_MAX == UINT32_MAX) || \\\n',
        '#if (defined(_WIN32) && defined(_M_X64)) || (defined(__ANDROID__) && defined(__x86_64__)) || \\\n    (defined(__EMSCRIPTEN__) && UINTPTR_MAX == UINT32_MAX) || \\\n'),
    'bcl/coreclr-net10/platform/kernel32.cpp': (
        '    if (::futimes(fd, times) != 0)',
        '''#if defined(__ANDROID__)
    const timespec precise_times[2] = {{times[0].tv_sec, static_cast<long>(times[0].tv_usec) * 1000},
                                      {times[1].tv_sec, static_cast<long>(times[1].tv_usec) * 1000}};
    if (::futimens(fd, precise_times) != 0)
#else
    if (::futimes(fd, times) != 0)
#endif'''),
    'bcl/coreclr-net10/platform/rt_sys.cpp': (
        '#elif defined(__GLIBC__)\n    char* msg = ::strerror_r',
        '#elif defined(__GLIBC__) || (defined(__ANDROID__) && defined(_GNU_SOURCE))\n    char* msg = ::strerror_r'),
}
diff, hashes = [], {}
for relative, (before, after) in changes.items():
    path = destination / 'src/runtime' / relative
    original = path.read_text(encoding='utf-8')
    if original.count(before) != 1:
        raise RuntimeError('Unexpected runtime source context: ' + relative)
    updated = original.replace(before, after)
    path.write_text(updated, encoding='utf-8', newline='\n')
    subprocess.run([str(args.source / 'tools/clang-format/clang-format.exe'), '-i',
                    '--style=file:' + str(args.source / '.clang-format'), str(path)], check=True)
    updated = path.read_text(encoding='utf-8')
    hashes[relative] = {'before': hashlib.sha256(original.encode()).hexdigest(), 'after': hashlib.sha256(updated.encode()).hexdigest()}
    name = 'src/runtime/' + relative
    diff.extend(difflib.unified_diff(original.splitlines(True), updated.splitlines(True), 'a/' + name, 'b/' + name))
patch = ROOT / 'runtime_patches'
patch.mkdir(exist_ok=True)
(patch / 'android-posix.patch').write_text(''.join(diff), encoding='utf-8', newline='\n')
(destination / 'patches.json').write_text(json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
print('Prepared Android runtime staging:', destination)

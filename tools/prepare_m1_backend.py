"""Prepare the publication-only Godot backend and typed reverse callbacks."""
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
godot = ROOT / 'extern/godot'
module = godot / 'modules/mono'
patches = ROOT / 'godot_patches/m1'
for name in ['leanclr_backend.h', 'leanclr_backend.cpp']:
    shutil.copyfile(patches / name, module / name)
cache = (module / 'mono_gd/gd_mono_cache.h').read_text()
fields = re.findall(r'\tFunc\w+ (\w+);', cache)
assert len(fields) == 37
managed = (module / 'glue/GodotSharp/GodotSharp/Core/Bridge/ManagedCallbacks.cs').read_text()
lines = ['bool bind_callbacks(LeanclrModuleDef *module, GDMonoCache::ManagedCallbacks &callbacks) {']
for index, field in enumerate(fields):
    signature = re.search(r'public delegate\* unmanaged<(.*?)> ' + field + r';', managed).group(1)
    depth = 0
    count = 0
    for char in signature:
        if char == '<': depth += 1
        elif char == '>': depth -= 1
        elif char == ',' and depth == 0: count += 1
    cls, method = field.split('_', 1)
    namespace = 'Godot.Bridge' if cls in ['ScriptManagerBridge', 'CSharpInstanceBridge', 'GCHandleBridge'] else 'Godot'
    lines.append(f' if (!bind({index}, module, "{namespace}.{cls}", "{method}", {count})) return false;')
    lines.append(f' callbacks.{field} = Callback<{index}, decltype(callbacks.{field})>::invoke;')
lines += [' return true;', '}']
(module / 'leanclr_backend_callbacks.inc').write_text('\n'.join(lines) + '\n', encoding='utf-8')
gdmono = module / 'mono_gd/gd_mono.cpp'
text = gdmono.read_text()
if 'leanclr_godot::initialize()' not in text:
    text = '#ifdef LEANCLR_GODOT\n#include "../leanclr_backend.h"\n#endif\n' + text
    text = text.replace('bool GDMono::should_initialize() {', '''bool GDMono::should_initialize() {
#ifdef LEANCLR_GODOT
 return true; // This is a dedicated LeanCLR publication template.
#endif''')
    text = text.replace('void GDMono::initialize() {', '''void GDMono::initialize() {
#ifdef LEANCLR_GODOT
 runtime_initialized = leanclr_godot::initialize();
 initialized = runtime_initialized;
 ERR_FAIL_COND_MSG(!initialized, "LeanCLR publication backend failed to initialize.");
 return;
#endif''')
    text = text.replace('GDMono::~GDMono() {', '''GDMono::~GDMono() {
#ifdef LEANCLR_GODOT
 leanclr_godot::shutdown();
#endif''')
    gdmono.write_text(text, encoding='utf-8', newline='\n')
text = gdmono.read_text().replace('OS::get_singleton()->has_feature("leanclr")', 'true').replace('ProjectSettings::get_singleton()->has_custom_feature("leanclr")', 'true')
gdmono.write_text(text, encoding='utf-8', newline='\n')
scsub = module / 'SCsub'
text = scsub.read_text()
if 'LEANCLR_GODOT_RUNTIME' in text:
    text = text.split('\n# Publication-only backend;')[0]
if 'LEANCLR_GODOT_RUNTIME' not in text:
    text += '''
# Publication-only backend; editor builds retain the official .NET host.
import os
leanclr_runtime = os.environ.get("LEANCLR_GODOT_RUNTIME")
if leanclr_runtime and not env.editor_build:
    env_mono.Append(CPPDEFINES=["LEANCLR_GODOT", "LEANCLR_STATIC"])
    env_mono.Append(CPPPATH=[os.path.join(os.environ["LEANCLR_GODOT_SOURCE"], "src/runtime/public")])
    if env["platform"] == "windows":
        env.Append(LIBS=[env.File(os.path.join(leanclr_runtime, "Release/leanclr-godot-calli.lib")),
                        env.File(os.path.join(leanclr_runtime, "runtime/Release/leanclr.lib"))])
        env.Append(LINKFLAGS=["bcrypt.lib"])
    else:
        env.Append(LIBS=[env.File(os.path.join(leanclr_runtime, "libleanclr-godot-calli.a")),
                        env.File(os.path.join(leanclr_runtime, "runtime/libleanclr.a"))])
'''
    scsub.write_text(text, encoding='utf-8', newline='\n')
registry = ROOT / 'build/m1/calli/modules.cpp'
registry.write_text('''// Generated registry; no runtime object layout is consumed by the host.
#include "metadata/rt_metadata.h"
extern const leanclr::metadata::RtCalliBridge g_calli_bridges[];
extern const uint32_t g_calli_bridge_count;
#ifdef LEANCLR_GODOT_GAMEPLAY_AOT
extern leanclr::metadata::RtAotModulesData g_aot_modules_data;
#endif
extern "C" const void* leanclr_godot_m1_modules() {
#ifdef LEANCLR_GODOT_GAMEPLAY_AOT
 return &g_aot_modules_data;
#else
 static const leanclr::metadata::RtAotModulesData data{nullptr, 0, nullptr, 0, g_calli_bridges, g_calli_bridge_count};
 return &data;
#endif
}
#ifndef LEANCLR_GODOT_GAMEPLAY_AOT
extern "C" void leanclr_godot_aot_report() {}
#endif
''', encoding='utf-8')
print('Prepared M1 backend and', len(fields), 'typed reverse callbacks')

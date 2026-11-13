param(
    [string]$RuntimeSource = (Join-Path $PSScriptRoot '../extern/leanclr'),
    [string]$Emsdk = (Join-Path $PSScriptRoot '../.tools/emsdk'),
    [int]$Jobs = 8
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$RuntimeSource = (Resolve-Path $RuntimeSource).Path
$logs = "$root/build/m3"
New-Item -ItemType Directory -Force $logs | Out-Null
function Run([string]$program, [string[]]$arguments, [string]$name) {
    $preference = $ErrorActionPreference
    try { $ErrorActionPreference = 'Continue'; & $program @arguments *> "$logs/$name.log"; $code = $LASTEXITCODE }
    finally { $ErrorActionPreference = $preference }
    if ($code -ne 0) { throw "$program failed: $code (see $logs/$name.log)" }
}
$env:EMSDK_QUIET = '1'
& "$Emsdk/emsdk_env.ps1"
Run 'python' @("$PSScriptRoot/prepare_m1_backend.py") 'prepare-backend'
Run 'python' @("$PSScriptRoot/prepare_portable_backend.py") 'prepare-portable'
$formatter = "$RuntimeSource/tools/clang-format/clang-format.exe"
$godot = "$root/extern/godot"
Run $formatter @('-i', "--style=file:$godot/.clang-format", "$godot/modules/mono/leanclr_backend.cpp", "$godot/modules/mono/leanclr_backend.h",
    "$godot/modules/mono/leanclr_backend_callbacks.inc", "$godot/modules/mono/mono_gd/gd_mono.cpp") 'format-backend'
Run $formatter @('-i', "--style=file:$RuntimeSource/.clang-format", "$root/build/m1/calli/modules.cpp") 'format-registry'
Run 'emcmake.bat' @('cmake', '-S', "$root/native/m1", '-B', "$logs/runtime", '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release', "-DLEANCLR_SOURCE_DIR=$RuntimeSource") 'configure-runtime'
Run 'cmake' @('--build', "$logs/runtime", '--parallel', "$Jobs") 'build-runtime'
$env:PYTHONPATH = "$root/.tools/scons"
$env:LEANCLR_GODOT_RUNTIME = "$logs/runtime"
$env:LEANCLR_GODOT_SOURCE = $RuntimeSource
Run 'python' @('-m', 'SCons', '-C', $godot, 'platform=web', 'target=template_release', 'arch=wasm32',
    'module_mono_enabled=yes', 'modules_enabled_by_default=no', 'module_gdscript_enabled=yes', 'module_freetype_enabled=yes',
    'module_svg_enabled=yes', 'module_text_server_fb_enabled=yes', 'module_godot_physics_2d_enabled=yes',
    'threads=no', 'dlink_enabled=no', 'initial_memory=128', 'debug_symbols=no', 'optimize=none', 'use_lto=no',
    'extra_suffix=leanclr_m3', "-j$Jobs") 'build-template'
Write-Host 'Web LeanCLR publication template built.'

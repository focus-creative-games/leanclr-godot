param(
    [string]$RuntimeSource = (Join-Path $PSScriptRoot '../extern/leanclr'),
    [string]$GodotMono = (Join-Path $PSScriptRoot '../../Godot_v4.7.2-stable_mono_win64'),
    [string]$Sample = (Join-Path $PSScriptRoot '../samples/dotnet'),
    [int]$Jobs = 8
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$RuntimeSource = (Resolve-Path $RuntimeSource).Path
$log = "$root/build/m1"
New-Item -ItemType Directory -Force $log | Out-Null
function Run([string]$program, [string[]]$arguments, [string]$name) {
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $program @arguments *> "$log/$name.log"
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $savedPreference }
    if ($code -ne 0) { throw "$program failed: $code (see $log/$name.log)" }
}
Run 'python' @("$PSScriptRoot/prepare_m1_managed.py", '--godot-mono', $GodotMono, '--sample', $Sample) 'managed-build'
Run 'dotnet' @('build', "$RuntimeSource/src/leanaot/LeanAOT/LeanAOT.csproj", '-c', 'Release', '--nologo') 'leanaot-build'
$aot = "$RuntimeSource/out/dotnet/LeanAOT/Release/net8.0/LeanAOT.dll"
Run 'dotnet' @($aot, '--leanaot-runtime-api-profile', 'coreclr-net10',
    '-d', "$root/build/m1/signature-fixture/bin/Release/net10.0", '-d', 'C:/Program Files/dotnet/shared/Microsoft.NETCore.App/10.0.8',
    '-a', 'GodotSharpEditor', '-o', "$root/build/m1/calli", '--calli-bridges-only') 'calli-generate'
$inventory = Get-Content "$root/build/m1/calli/calli_bridges.json" -Raw | ConvertFrom-Json
if ($inventory.bridge_count -le 0 -or @($inventory.sites | Where-Object status -ne 'generated').Count -ne 0) { throw 'Incomplete native calli signature catalog.' }
Run 'python' @("$PSScriptRoot/prepare_m1_backend.py") 'prepare-backend'
$formatter = "$RuntimeSource/tools/clang-format/clang-format.exe"
$godot = "$root/extern/godot"
Run $formatter @('-i', "--style=file:$godot/.clang-format", "$godot/modules/mono/leanclr_backend.cpp", "$godot/modules/mono/leanclr_backend.h",
    "$godot/modules/mono/leanclr_backend_callbacks.inc", "$godot/modules/mono/mono_gd/gd_mono.cpp") 'format-backend'
Run $formatter @('-i', "--style=file:$RuntimeSource/.clang-format", "$root/build/m1/calli/modules.cpp", "$root/build/m1/calli/calli_bridges.cpp",
    "$root/build/m1/calli/calli_bridge_types.h") 'format-bridges'
Run 'cmake' @('-S', "$root/native/m1", '-B', "$root/build/m1/runtime", '-G', 'Visual Studio 17 2022', '-A', 'x64', "-DLEANCLR_SOURCE_DIR=$RuntimeSource") 'runtime-configure'
Run 'cmake' @('--build', "$root/build/m1/runtime", '--config', 'Release', '--parallel', "$Jobs") 'runtime-build'
$previousPythonPath = $env:PYTHONPATH
$previousRuntime = $env:LEANCLR_GODOT_RUNTIME
$previousSource = $env:LEANCLR_GODOT_SOURCE
try {
    $env:PYTHONPATH = "$root/.tools/scons"
    $env:LEANCLR_GODOT_RUNTIME = "$root/build/m1/runtime"
    $env:LEANCLR_GODOT_SOURCE = $RuntimeSource
    Run 'python' @('-m', 'SCons', '-C', $godot, 'platform=windows', 'target=template_release', 'arch=x86_64',
        'module_mono_enabled=yes', 'modules_enabled_by_default=no', 'module_gdscript_enabled=yes', 'module_freetype_enabled=yes',
        'module_svg_enabled=yes', 'module_text_server_fb_enabled=yes', 'module_godot_physics_2d_enabled=yes',
        'vulkan=no', 'opengl3=yes', 'd3d12=no', 'accesskit=no', 'angle=no', 'debug_symbols=no', 'optimize=none', 'use_lto=no', 'extra_suffix=leanclr_m1', "-j$Jobs") 'template-build'
} finally {
    $env:PYTHONPATH = $previousPythonPath
    $env:LEANCLR_GODOT_RUNTIME = $previousRuntime
    $env:LEANCLR_GODOT_SOURCE = $previousSource
}
Run 'dotnet' @('build', "$root/tools/managed-info/ManagedInfo.csproj", '-c', 'Release', '--nologo') 'managed-info-build'
Write-Host 'M1 Windows template and publication assemblies built.'

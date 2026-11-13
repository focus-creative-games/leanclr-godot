param(
    [string]$GodotMono = (Join-Path $PSScriptRoot '../../Godot_v4.7.2-stable_mono_win64'),
    [int]$Jobs = 8
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$GodotMono = (Resolve-Path $GodotMono).Path
$source = "$root/extern/godot"
$logs = "$root/build/m0"
New-Item -ItemType Directory -Force $logs | Out-Null
function Run([string]$program, [string[]]$arguments, [string]$log) {
    & $program @arguments *> $log
    if ($LASTEXITCODE -ne 0) { throw "$program failed: $LASTEXITCODE (see $log)" }
}
Run 'python' @("$PSScriptRoot/prepare_godot.py") "$logs/prepare-godot.log"
if (-not (Test-Path "$root/.tools/scons/SCons/__init__.py")) {
    Run 'python' @('-m', 'pip', 'install', '--target', "$root/.tools/scons", 'SCons==4.8.1') "$logs/scons-install.log"
}
Run 'python' @("$PSScriptRoot/prepare_m0_exporter.py") "$logs/prepare-exporter.log"
$formatter = "$root/extern/leanclr/tools/clang-format/clang-format.exe"
if (-not (Test-Path $formatter)) { throw 'The pinned LeanCLR clang-format tool is required.' }
Run $formatter @('-i', "--style=file:$source/.clang-format", "$source/platform/web/export/export_plugin.cpp") "$logs/format-exporter.log"
$savedPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = "$root/.tools/scons"
    Run 'python' @('-m', 'SCons', '-C', $source, 'platform=windows', 'target=editor', 'arch=x86_64',
        'module_mono_enabled=yes', 'modules_enabled_by_default=no', 'module_gdscript_enabled=yes',
        'module_freetype_enabled=yes', 'module_regex_enabled=yes', 'module_svg_enabled=yes', 'module_text_server_fb_enabled=yes',
        'vulkan=no', 'opengl3=no', 'd3d12=no', 'debug_symbols=no', 'optimize=none', 'use_lto=no',
        'extra_suffix=leanclr_m0', "-j$Jobs") "$logs/exporter-native-build.log"
} finally { $env:PYTHONPATH = $savedPythonPath }
New-Item -ItemType Directory -Force "$source/bin/GodotSharp" | Out-Null
New-Item -ItemType File -Force "$source/bin/._sc_" | Out-Null
Get-ChildItem -LiteralPath "$GodotMono/GodotSharp" | Copy-Item -Destination "$source/bin/GodotSharp" -Recurse -Force
Run 'python' @('-c', 'import sys; sys.path.insert(0, sys.argv[1]); import build_assemblies; build_assemblies.generate_sdk_package_versions()',
    "$source/modules/mono/build_scripts") "$logs/generate-sdk-metadata.log"
Run 'dotnet' @('build', "$source/modules/mono/editor/GodotTools/GodotTools/GodotTools.csproj", '-c', 'Debug',
    "-p:GodotOutputDataDir=$source/bin/GodotSharp", "-p:GodotApiAssembliesDir=$source/bin/GodotSharp/Api/Debug",
    '--nologo') "$logs/exporter-managed-build.log"
Write-Host "M0 helper ready: $source/bin/godot.windows.editor.x86_64.leanclr_m0.mono.console.exe"

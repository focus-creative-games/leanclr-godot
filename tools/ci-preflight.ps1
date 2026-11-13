$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$required = @(
    'extern/godot/.leanclr-source.json',
    'extern/godot/bin/godot.windows.editor.x86_64.leanclr_m0.mono.console.exe',
    '.tools/scons/SCons/__init__.py', '.tools/browser/playwright/__init__.py',
    '.tools/emsdk/emsdk_env.ps1', '.tools/android-sdk/ndk/29.0.14206865/build/cmake/android.toolchain.cmake',
    'samples/dotnet/.godot/mono', 'samples/semantics/.godot/mono', 'samples/extended/.godot/mono'
)
foreach ($path in $required) {
    if (-not (Test-Path (Join-Path $root $path))) { throw "Prepare the SDK in this runner checkout before dispatching CI. Missing: $path" }
}
$editor = Join-Path $root '../Godot_v4.7.2-stable_mono_win64/Godot_v4.7.2-stable_mono_win64_console.exe'
if (-not (Test-Path $editor)) { throw 'The pinned official .NET editor must be installed alongside this SDK checkout.' }
foreach ($program in @('python', 'dotnet', 'cmake', 'java')) { $null = Get-Command $program -ErrorAction Stop }
Write-Host 'CI_PREFLIGHT_OK prepared SDK checkout and local toolchain'

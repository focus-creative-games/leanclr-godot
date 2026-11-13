param(
    [ValidateSet('native', 'web')][string]$Target = 'native',
    [string]$RuntimeSource = (Join-Path $PSScriptRoot '../extern/leanclr'),
    [string]$Emsdk = (Join-Path $PSScriptRoot '../.tools/emsdk'),
    [string]$Godot = (Join-Path $PSScriptRoot '../../v4.7.2-stable_win64/Godot_v4.7.2-stable_win64_console.exe')
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
if (-not (Test-Path (Join-Path $RuntimeSource 'src/runtime/CMakeLists.txt'))) {
    throw 'LeanCLR sources are missing. Run git submodule update --init --recursive, or pass -RuntimeSource with another checkout.'
}
$RuntimeSource = (Resolve-Path $RuntimeSource).Path
function Run([string]$program, [string[]]$arguments) {
    & $program @arguments
    if ($LASTEXITCODE -ne 0) { throw "$program failed: $LASTEXITCODE" }
}
Run 'python' @("$PSScriptRoot/prepare_dependencies.py")
$managedTarget = if ($Target -eq 'web') { 'wasm' } else { 'native' }
Run 'python' @("$PSScriptRoot/prepare_managed.py", '--runtime-source', $RuntimeSource, '--target', $managedTarget)
if ($Target -eq 'native') {
    $build = "$root/build/native"
    Run 'cmake' @('-S', $root, '-B', $build, '-G', 'Visual Studio 17 2022', '-A', 'x64', "-DLEANCLR_SOURCE_DIR=$RuntimeSource")
    Run 'cmake' @('--build', $build, '--config', 'Release', '--parallel', '8')
} else {
    $build = "$root/build/wasm-4.0.20"
    if (-not (Test-Path "$Emsdk/emsdk_env.ps1")) {
        throw 'Prepare Emscripten 4.0.20 first: python tools/prepare_web.py'
    }
    $env:EMSDK_QUIET = '1'
    & "$Emsdk/emsdk_env.ps1"
    Run 'emcmake.bat' @('cmake', '-S', $root, '-B', $build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release', "-DLEANCLR_SOURCE_DIR=$RuntimeSource")
    Run 'cmake' @('--build', $build, '--parallel', '8')
}
Run $Godot @('--headless', '--path', "$root/demo", '--editor', '--import')
Write-Host "Built $Target. Run the demo or export with tools/export.ps1."

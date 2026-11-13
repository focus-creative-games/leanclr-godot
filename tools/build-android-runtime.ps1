param(
    [string]$RuntimeSource = (Join-Path $PSScriptRoot '../extern/leanclr'),
    [int]$Jobs = 8
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$RuntimeSource = (Resolve-Path $RuntimeSource).Path
$logs = "$root/build/android"
$sdk = "$root/.tools/android-sdk"
$ndk = "$sdk/ndk/29.0.14206865"
New-Item -ItemType Directory -Force $logs | Out-Null
function Run([string]$program, [string[]]$arguments, [string]$name) {
    $preference = $ErrorActionPreference
    try { $ErrorActionPreference = 'Continue'; & $program @arguments *> "$logs/$name.log"; $code = $LASTEXITCODE }
    finally { $ErrorActionPreference = $preference }
    if ($code -ne 0) { throw "$program failed: $code (see $logs/$name.log)" }
}
if (-not (Test-Path "$ndk/build/cmake/android.toolchain.cmake")) { throw 'Run python tools/prepare_android.py first.' }
Run 'python' @("$PSScriptRoot/prepare_android_runtime.py", '--source', $RuntimeSource) 'prepare-runtime'
$patchedSource = "$logs/leanclr-source"
Run 'python' @("$PSScriptRoot/prepare_m1_backend.py") 'prepare-backend'
Run 'python' @("$PSScriptRoot/prepare_portable_backend.py") 'prepare-portable'
$formatter = "$RuntimeSource/tools/clang-format/clang-format.exe"
Run $formatter @('-i', "--style=file:$RuntimeSource/.clang-format", "$patchedSource/src/runtime/bcl/coreclr-net10/platform/kernel32.cpp",
    "$patchedSource/src/runtime/bcl/coreclr-net10/platform/rt_sys.cpp") 'format-runtime'
$godot = "$root/extern/godot"
Run $formatter @('-i', "--style=file:$godot/.clang-format", "$godot/modules/mono/leanclr_backend.cpp", "$godot/modules/mono/leanclr_backend.h",
    "$godot/modules/mono/leanclr_backend_callbacks.inc", "$godot/modules/mono/mono_gd/gd_mono.cpp") 'format-backend'
Run $formatter @('-i', "--style=file:$RuntimeSource/.clang-format", "$root/build/m1/calli/modules.cpp") 'format-registry'
Run 'cmake' @('-S', "$root/native/m1", '-B', "$logs/runtime-x86_64", '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
    "-DCMAKE_TOOLCHAIN_FILE=$ndk/build/cmake/android.toolchain.cmake", '-DANDROID_ABI=x86_64', '-DANDROID_PLATFORM=android-24',
    '-DANDROID_STL=c++_shared', "-DLEANCLR_SOURCE_DIR=$patchedSource") 'configure-runtime'
Run 'cmake' @('--build', "$logs/runtime-x86_64", '--parallel', "$Jobs") 'build-runtime'
$env:ANDROID_HOME = $sdk
$env:ANDROID_SDK_ROOT = $sdk
$env:PYTHONPATH = "$root/.tools/scons"
$env:LEANCLR_GODOT_RUNTIME = "$logs/runtime-x86_64"
$env:LEANCLR_GODOT_SOURCE = $patchedSource
Run 'python' @('-m', 'SCons', '-C', $godot, 'platform=android', 'target=template_release', 'arch=x86_64',
    'module_mono_enabled=yes', 'modules_enabled_by_default=no', 'module_gdscript_enabled=yes', 'module_freetype_enabled=yes',
    'module_svg_enabled=yes', 'module_text_server_fb_enabled=yes', 'module_godot_physics_2d_enabled=yes',
    'vulkan=no', 'opengl3=yes', 'debug_symbols=no', 'optimize=none', 'use_lto=no', 'extra_suffix=leanclr_m4', "-j$Jobs") 'build-template'
Write-Host 'Android x86_64 LeanCLR shared library built.'

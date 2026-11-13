param(
    [ValidateSet('native', 'web')][string]$Target = 'native',
    [string]$RuntimeSource = (Join-Path $PSScriptRoot '../extern/leanclr'),
    [string]$Emsdk = (Join-Path $PSScriptRoot '../.tools/emsdk'),
    [switch]$BaselineOnly
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$RuntimeSource = (Resolve-Path $RuntimeSource).Path
$output = "$root/build/m0/abi-managed"
New-Item -ItemType Directory -Force $output | Out-Null
function Run([string]$program, [string[]]$arguments) {
    & $program @arguments
    if ($LASTEXITCODE -ne 0) { throw "$program failed: $LASTEXITCODE" }
}
$sdk = dotnet --list-sdks | Where-Object { $_ -match '^10\.' } | Select-Object -Last 1
if ($sdk -notmatch '^(\S+) \[(.+)\]$') { throw '.NET 10 SDK is required.' }
$compiler = Join-Path $Matches[2] "$($Matches[1])/Roslyn/bincore/csc.dll"
$nativeBcl = 'C:/Program Files/dotnet/shared/Microsoft.NETCore.App/10.0.8'
Run 'dotnet' @($compiler, '/nologo', '/noconfig', '/nostdlib+', '/target:library', '/optimize+',
    "/r:$nativeBcl/System.Private.CoreLib.dll", "/out:$output/M0.Contracts.dll", "$root/tests/m0/Contracts.cs")
if ($Target -eq 'native') {
    $build = "$root/build/native"
    $bcl = $nativeBcl
    Run 'cmake' @('-S', $root, '-B', $build, '-G', 'Visual Studio 17 2022', '-A', 'x64',
        "-DLEANCLR_SOURCE_DIR=$RuntimeSource", '-DLEANCLR_GODOT_M0_PROBES=ON')
    $program = "$build/Release/m0-public-abi.exe"
} else {
    $env:EMSDK_QUIET = '1'
    & "$Emsdk/emsdk_env.ps1"
    $build = "$root/build/wasm-4.0.20"
    $bcl = "$RuntimeSource/out/net10-runtime-win-x86/runtimes/win-x86/lib/net10.0"
    Run 'emcmake.bat' @('cmake', '-S', $root, '-B', $build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
        "-DLEANCLR_SOURCE_DIR=$RuntimeSource", '-DLEANCLR_GODOT_M0_PROBES=ON')
    $program = 'node'
}
Run 'cmake' @('--build', $build, '--config', 'Release', '--target', 'm0-public-abi', '--parallel', '8')
$arguments = @($output, $bcl)
if ($Target -eq 'web') {
    $managedRelative = [IO.Path]::GetRelativePath($root, $output).Replace('\', '/')
    $bclRelative = [IO.Path]::GetRelativePath($root, $bcl).Replace('\', '/')
    if ([IO.Path]::IsPathRooted($bclRelative)) { throw 'The Wasm probe requires BCL files on the same drive as the repository.' }
    $arguments = @("$build/m0-public-abi.js", $managedRelative, $bclRelative)
}
if (-not $BaselineOnly) { $arguments += '--callbacks' }
Push-Location $root
try {
    & $program @arguments | Tee-Object "$root/build/m0/abi-$Target.log"
    $code = $LASTEXITCODE
    if ($code -eq 3) {
        Write-Host 'M0 ABI callback checks were skipped or a contract failed. This is not a passing milestone.'
        exit 3
    }
    if ($code -ne 0) { throw "M0 ABI probe failed: $code" }
} finally { Pop-Location }

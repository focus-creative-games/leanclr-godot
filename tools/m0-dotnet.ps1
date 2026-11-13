param(
    [string]$Godot = (Join-Path $PSScriptRoot '../../Godot_v4.7.2-stable_mono_win64/Godot_v4.7.2-stable_mono_win64_console.exe')
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$sample = Join-Path $root 'samples/dotnet'
$Godot = (Resolve-Path $Godot).Path
$feed = Join-Path (Split-Path $Godot) 'GodotSharp/Tools/nupkgs'
if (-not (Test-Path "$feed/Godot.NET.Sdk.4.7.2.nupkg")) { throw 'Godot 4.7.2 .NET SDK packages are required.' }
$escapedFeed = [System.Security.SecurityElement]::Escape($feed)
@"
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources><clear /><add key="godot-local" value="$escapedFeed" /></packageSources>
</configuration>
"@ | Set-Content "$sample/NuGet.Config" -Encoding utf8
$logs = Join-Path $root 'build/m0/dotnet'
New-Item -ItemType Directory -Force $logs | Out-Null
function Run([string]$program, [string[]]$arguments, [string]$log) {
    $output = & $program @arguments 2>&1
    $exitCode = $LASTEXITCODE
    $output | Set-Content $log -Encoding utf8
    $output | Write-Host
    if ($exitCode -ne 0) { throw "$program failed: $exitCode (see $log)" }
    return ($output -join "`n")
}
Push-Location $sample
try {
    $version = Run $Godot @('--version') "$logs/version.log"
    if ($version -notmatch '4\.7\.2\.stable\.mono\.official\.ed1daf0bf') { throw "Unexpected editor: $version" }
    foreach ($revision in @(1, 2)) {
        $null = Run 'dotnet' @('build', 'Gameplay.csproj', '-c', 'Debug', "-p:M0Revision=$revision", '--nologo') "$logs/build-$revision.log"
        $null = Run $Godot @('--headless', '--path', $sample, '--editor', '--import') "$logs/import-$revision.log"
        $run = Run $Godot @('--headless', '--path', $sample, '--', '--m0-smoke') "$logs/run-$revision.log"
        if ($run -notmatch "M0_DOTNET_OK revision=$revision instances=1 x=8") { throw 'The current DLL or clean process state was not observed.' }
    }
    $null = Run 'dotnet' @('build', 'Gameplay.csproj', '-c', 'Debug', '-p:M0Revision=1', '--nologo') "$logs/build-final.log"
    Write-Host 'M0_DOTNET_REPLAY_OK: both process launches loaded their newly built DLL.'
} finally { Pop-Location }

param(
    [switch]$Exported,
    [switch]$Capture,
    [string]$Godot = (Join-Path $PSScriptRoot '../../v4.7.2-stable_win64/Godot_v4.7.2-stable_win64_console.exe')
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$log = "$root/build/smoke-$(if ($Exported) {'exported'} else {'editor-runtime'}).log"
$arguments = @('--log-file', $log)
if (-not $Capture) { $arguments += '--headless' }
if ($Exported) { $Godot = "$root/build/export/native/leanclr-demo.exe" }
else { $arguments += @('--path', "$root/demo") }
$arguments += @('--', '--smoke-test')
if ($Capture) { $arguments += "--capture=$root/build/desktop-demo.png" }
$process = Start-Process -FilePath $Godot -ArgumentList $arguments -PassThru -WindowStyle Hidden
if (-not $process.WaitForExit(60000)) {
    $process.Kill()
    throw 'Demo smoke timed out'
}
$process.Refresh()
$text = Get-Content -Raw $log
Write-Host $text
if ($process.ExitCode -ne 0 -or $text -notmatch 'LEANCLR_SMOKE_OK' -or $text -notmatch 'LEANCLR_STOPPED files=2/2') {
    throw 'Demo smoke did not pass gameplay and lifecycle checks'
}

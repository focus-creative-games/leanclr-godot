param(
    [string]$Executable = (Join-Path $PSScriptRoot '../build/export/m1/windows/leanclr-node2d.exe'),
    [switch]$Visible
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$Executable = (Resolve-Path $Executable).Path
$suffix = if ($Visible) { 'visible' } else { 'headless' }
$log = "$root/build/m1/smoke-$suffix.log"
$arguments = @('--max-fps', '10', '--log-file', $log, '--', '--m0-smoke')
if (-not $Visible) { $arguments = @('--headless') + $arguments }
$start = @{FilePath=$Executable; ArgumentList=$arguments; PassThru=$true;
    RedirectStandardOutput="$root/build/m1/stdout-$suffix.log"; RedirectStandardError="$root/build/m1/stderr-$suffix.log"}
if (-not $Visible) { $start.WindowStyle = 'Hidden' }
$process = Start-Process @start
$modules = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$watch = [Diagnostics.Stopwatch]::StartNew()
$peakWorkingSet = 0L
while (-not $process.HasExited) {
    $peakWorkingSet = [Math]::Max($peakWorkingSet, $process.PeakWorkingSet64)
    try { foreach ($module in $process.Modules) { $null = $modules.Add($module.ModuleName) } } catch { }
    if ($watch.Elapsed.TotalSeconds -gt 30) { $process.Kill(); throw 'M1 smoke timed out' }
    $null = $process.WaitForExit(10)
    $process.Refresh()
}
$process.Refresh()
$text = Get-Content $log -Raw
if ($process.ExitCode -ne 0 -or $text -notmatch 'LEANCLR_GODOT_READY backend=LeanCLR' -or
    $text -notmatch 'NODE2D_SMOKE_OK instances=1 frames=4 x=8 speed=120') { throw "M1 smoke failed; see $log" }
if ($Visible -and $text -notmatch 'draws=[1-9][0-9]*') { throw 'Visible smoke did not run C# drawing.' }
if ($modules.Count -lt 10) { throw 'Insufficient process module observations.' }
foreach ($forbidden in @('coreclr.dll', 'hostfxr.dll', 'hostpolicy.dll', 'clr.dll')) {
    if ($modules.Contains($forbidden)) { throw "Published process loaded $forbidden" }
}
$receipt = @{status='passed'; mode=$suffix; elapsed_ms=$watch.Elapsed.TotalMilliseconds;
    peak_working_set=$peakWorkingSet; modules=@($modules | Sort-Object); executable=$Executable}
$receipt | ConvertTo-Json -Depth 4 | Set-Content "$root/build/m1/smoke-$suffix.json" -Encoding utf8
Write-Host $text
Write-Host "M1_SMOKE_OK mode=$suffix no_coreclr=true"

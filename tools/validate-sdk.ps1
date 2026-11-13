param([switch]$Build)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$stamp = [Guid]::NewGuid().ToString('N').Substring(0, 8)
$receipt = "$root/build/ci/$stamp"
New-Item -ItemType Directory -Force $receipt | Out-Null
$results = @()
function Run([string]$program, [string[]]$arguments) {
    & $program @arguments
    if ($LASTEXITCODE -ne 0) { throw "$program failed: $LASTEXITCODE" }
}
foreach ($target in @('win64', 'html5', 'android')) {
    foreach ($sample in @('dotnet', 'semantics', 'extended')) {
        $output = "$receipt/$target-$sample"
        $arguments = @("$PSScriptRoot/publish.py", '--target', $target, '--sample', "$root/samples/$sample", '--output', $output)
        if ($Build -and $sample -eq 'dotnet') { $arguments += '--build' }
        if ($target -eq 'android' -and $sample -eq 'dotnet') { $arguments += '--smoke' }
        Run 'python' $arguments
        $expected = if ($sample -eq 'dotnet') { 'NODE2D_SMOKE_OK instances=1 frames=4 x=8 speed=120' } elseif ($sample -eq 'semantics') { 'M2_SEMANTICS_OK checks=15 observed=31' } else { 'M5_EXTENDED_OK checks=11' }
        if ($target -eq 'win64') {
            $arguments = @('--headless', '--verbose')
            if ($sample -eq 'dotnet') { $arguments += @('--', '--m0-smoke') }
            $previous = $ErrorActionPreference
            try {
                $ErrorActionPreference = 'Continue'
                $text = & "$output/leanclr-node2d.console.exe" @arguments 2>&1 | Out-String
                $code = $LASTEXITCODE
            } finally { $ErrorActionPreference = $previous }
            $text | Set-Content "$output/runtime.log" -Encoding utf8
            if ($code -ne 0 -or $text -notmatch [regex]::Escape($expected)) { throw "Windows contract failed: $sample" }
        } elseif ($target -eq 'html5') {
            Run 'python' @("$PSScriptRoot/test-web-runtime.py", '--directory', $output, '--expected', $expected, '--report-dir', "$output/validation")
        } else {
            Run 'python' @("$PSScriptRoot/test-android-runtime.py", "$output/demo.apk", '--sample', $sample, '--report-dir', "$output/validation")
        }
        $results += @{target=$target; sample=$sample; status='passed'; expected=$expected; output=$output}
    }
}
@{status='passed'; cases=$results} | ConvertTo-Json -Depth 5 | Set-Content "$receipt/report.json" -Encoding utf8
Write-Host "SDK_MATRIX_OK receipts=$receipt"

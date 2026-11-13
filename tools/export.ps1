param(
    [ValidateSet('native', 'web')][string]$Target = 'native',
    [string]$Godot = (Join-Path $PSScriptRoot '../../v4.7.2-stable_win64/Godot_v4.7.2-stable_win64_console.exe')
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$directory = "$root/build/export/$Target"
New-Item -ItemType Directory -Force $directory | Out-Null
$preset = if ($Target -eq 'web') { 'Web' } else { 'Windows' }
$output = if ($Target -eq 'web') { "$directory/index.html" } else { "$directory/leanclr-demo.exe" }
& $Godot --headless --path "$root/demo" --export-release $preset $output
if ($LASTEXITCODE -ne 0) { throw "Godot export failed: $LASTEXITCODE" }
if ($Target -eq 'web') {
    & python "$PSScriptRoot/post_export_web.py"
    if ($LASTEXITCODE -ne 0) { throw 'Web smoke shell setup failed' }
}
Copy-Item -Recurse -Force "$root/demo/managed/notices" "$directory/notices"

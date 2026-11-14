# Navigate the option screens in the real game and dump the screen. Usage: powershell -File tools/run_nav.ps1 <rom> <out_dir> <downs>
param([string]$Rom, [string]$OutDir, [int]$Downs)
$root = Split-Path -Parent $PSScriptRoot
$mesen = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\SourMesen.Mesen2*\Mesen.exe" | Select-Object -First 1).FullName
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -File | Remove-Item -Force
$out = ((Resolve-Path $OutDir).Path -replace '\\', '/') + '/'
$lua = Join-Path $OutDir "_run.lua"
(Get-Content (Join-Path $root "tests\nav_option.lua") -Raw) -replace 'C:/PLACEHOLDER/', $out -replace 'local DOWNS = 3', "local DOWNS = $Downs" | Set-Content $lua -Encoding ascii
$p = Start-Process $mesen -ArgumentList @('--testRunner', "`"$((Resolve-Path $Rom).Path)`"", "`"$((Resolve-Path $lua).Path)`"") -PassThru -WindowStyle Hidden
if (-not $p.WaitForExit(170000)) { $p.Kill(); "TIMEOUT" }
Get-Content (Join-Path $OutDir "nav.txt") | Select-Object -Last 6

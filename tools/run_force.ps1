# Run tests/force_state.lua on a ROM with a given forced game state. Usage: powershell -File tools/run_force.ps1 <rom> <out_dir> <state_hex>
param([string]$Rom, [string]$OutDir, [string]$State)
$root = Split-Path -Parent $PSScriptRoot
$mesen = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\SourMesen.Mesen2*\Mesen.exe" | Select-Object -First 1).FullName
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -File | Remove-Item -Force
$out = ((Resolve-Path $OutDir).Path -replace '\\', '/') + '/'
$lua = Join-Path $OutDir "_run.lua"
(Get-Content (Join-Path $root "tests\force_state.lua") -Raw) -replace 'C:/PLACEHOLDER/', $out -replace 'local FORCED = 0x19', "local FORCED = 0x$State" | Set-Content $lua -Encoding ascii
$p = Start-Process $mesen -ArgumentList @('--testRunner', "`"$((Resolve-Path $Rom).Path)`"", "`"$((Resolve-Path $lua).Path)`"") -PassThru -WindowStyle Hidden
if (-not $p.WaitForExit(120000)) { $p.Kill(); "TIMEOUT" }
Get-Content (Join-Path $OutDir "force.txt")

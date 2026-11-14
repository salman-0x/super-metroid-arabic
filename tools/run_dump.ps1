# Run the real game headless in Mesen with tests/dump_screens.lua and write VRAM/CGRAM/state dumps.
# Usage: powershell -File tools/run_dump.ps1 <rom> <out_dir>
param([string]$Rom, [string]$OutDir)
$root = Split-Path -Parent $PSScriptRoot
$mesen = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\SourMesen.Mesen2*\Mesen.exe" | Select-Object -First 1).FullName
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -File | Remove-Item -Force
$out = ((Resolve-Path $OutDir).Path -replace '\\', '/') + '/'
$lua = Join-Path $OutDir "_run.lua"
(Get-Content (Join-Path $root "tests\dump_screens.lua") -Raw) -replace 'C:/PLACEHOLDER/', $out | Set-Content $lua -Encoding ascii
$romPath = (Resolve-Path $Rom).Path
$p = Start-Process $mesen -ArgumentList @('--testRunner', "`"$romPath`"", "`"$((Resolve-Path $lua).Path)`"") -PassThru -WindowStyle Hidden
if ($p.WaitForExit(170000)) { "mesen exit=$($p.ExitCode)" } else { $p.Kill(); "TIMEOUT" }
Get-Content (Join-Path $OutDir "log.txt") | Select-String "DUMP"

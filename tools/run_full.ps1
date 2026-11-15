param([string]$Rom, [string]$Dir)
# Runs tests/nav_full.lua in Mesen headless on a stub ROM made by tools/make_save_full.py. Output (screenshots + full.txt) goes to $Dir.
$root = Split-Path -Parent $PSScriptRoot
$od = Join-Path $root $Dir
New-Item -ItemType Directory -Force $od | Out-Null
Get-ChildItem $od -File | Remove-Item -Force
$t = (Get-Content (Join-Path $root "tests\nav_full.lua") -Raw).Replace("C:/PLACEHOLDER/", (($od -replace '\\','/') + '/'))
Set-Content (Join-Path $od "_run.lua") $t -Encoding ascii
$mesen = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\SourMesen.Mesen2*\Mesen.exe" | Select-Object -First 1).FullName
$p = Start-Process $mesen -ArgumentList @('--testRunner', "`"$((Resolve-Path (Join-Path $root $Rom)).Path)`"", "`"$(Join-Path $od '_run.lua')`"") -PassThru -WindowStyle Hidden
if (-not $p.WaitForExit(400000)) { $p.Kill(); "TIMEOUT" }
"exit code: $($p.ExitCode)"

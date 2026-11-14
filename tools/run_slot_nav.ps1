param([string]$Rom, [string]$Dir, [string]$Plan, [string]$Dumps, [int]$Last = 1600)
# Runs tests/nav_slot.lua in Mesen headless: $Plan is Lua like "add(400,'start') add(490,'down')"; one VRAM/CGRAM/state dump per frame in $Dumps.
$root = Split-Path -Parent $PSScriptRoot
$od = Join-Path $root $Dir
New-Item -ItemType Directory -Force $od | Out-Null
Get-ChildItem $od -File | Remove-Item -Force
$t = Get-Content (Join-Path $root "tests\nav_slot.lua") -Raw
$d = (($Dumps -split ",") | ForEach-Object { "dumps[$_] = `"f$_`"" }) -join "`n"
$t = $t.Replace("C:/PLACEHOLDER/", (($od -replace '\\','/') + '/')).Replace("local LAST = 600", "local LAST = $Last").Replace("--@@PLAN@@", ($Plan + "`n" + $d))
Set-Content (Join-Path $od "_run.lua") $t -Encoding ascii
$mesen = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\SourMesen.Mesen2*\Mesen.exe" | Select-Object -First 1).FullName
$p = Start-Process $mesen -ArgumentList @('--testRunner', "`"$((Resolve-Path (Join-Path $root $Rom)).Path)`"", "`"$(Join-Path $od '_run.lua')`"") -PassThru -WindowStyle Hidden
if (-not $p.WaitForExit(280000)) { $p.Kill(); "TIMEOUT" }



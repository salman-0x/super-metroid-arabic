param([string]$Rom, [string]$Dir, [string]$Plan, [string]$Dumps, [int]$RelLast = 600, [int]$LastWait = 40000)
$root = Split-Path -Parent $PSScriptRoot
$od = Join-Path $root $Dir
New-Item -ItemType Directory -Force $od | Out-Null
Get-ChildItem $od -File | Remove-Item -Force
$t = Get-Content (Join-Path $root "tests\nav_game.lua") -Raw
$d = (($Dumps -split ",") | ForEach-Object { "dumps[$_] = `"g$_`"" }) -join "`n"
$t = $t.Replace("C:/PLACEHOLDER/", (($od -replace '\\','/') + '/')).Replace("LASTWAIT", "$LastWait").Replace("REL_LAST", "$RelLast").Replace("--@@PLAN@@", ($Plan + "`n" + $d))
Set-Content (Join-Path $od "_run.lua") $t -Encoding ascii
$mesen = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\SourMesen.Mesen2*\Mesen.exe" | Select-Object -First 1).FullName
$p = Start-Process $mesen -ArgumentList @('--testRunner', "`"$((Resolve-Path (Join-Path $root $Rom)).Path)`"", "`"$(Join-Path $od '_run.lua')`"") -PassThru -WindowStyle Hidden
if (-not $p.WaitForExit(560000)) { $p.Kill(); "TIMEOUT" }

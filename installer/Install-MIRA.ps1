<#
.SYNOPSIS
  Installs MIRA from the extracted offline package (no internet, no Python, no admin rights for a per-user install).
  Run from the extracted MIRA folder:  powershell -ExecutionPolicy Bypass -File .\Install-MIRA.ps1
.PARAMETER Target
  Install directory. Default: %LOCALAPPDATA%\Programs\MIRA. Use "$env:ProgramFiles\MIRA" from an elevated prompt
  for a machine-wide install. Documents, index and logs live in %LOCALAPPDATA%\MIRA and survive reinstalls.
.PARAMETER Start
  Start MIRA right after installing.
#>
param([string]$Target = "$env:LOCALAPPDATA\Programs\MIRA", [switch]$Start)
$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
if (-not (Test-Path "$src\runtime\python\python.exe") -or -not (Test-Path "$src\ovms\ovms.exe") -or -not (Test-Path "$src\models\config.json")) {
    throw "Run this script from the extracted MIRA package folder."
}
Write-Host "Installing MIRA to $Target"
if (Test-Path $Target) {
    if (Test-Path "$Target\Stop-MIRA.ps1") { & "$Target\Stop-MIRA.ps1" }
    Remove-Item -Recurse -Force $Target
}
New-Item -ItemType Directory -Force $Target | Out-Null
robocopy $src $Target /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "copy failed" }

& "$Target\runtime\python\python.exe" -I -c "import mira.app, mira.check; print('runtime ok, MIRA', __import__('mira').__version__)"
if ($LASTEXITCODE) { throw "The installed runtime does not start." }

$menu = Join-Path ([Environment]::GetFolderPath("Programs")) "MIRA"
New-Item -ItemType Directory -Force $menu | Out-Null
$shell = New-Object -ComObject WScript.Shell
$ps = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
foreach ($l in @(
        @("MIRA Wartungsassistent", "Start-MIRA.ps1", "MIRA starten: Modelle auf die NPU laden, Web-UI öffnen"),
        @("MIRA beenden", "Stop-MIRA.ps1", "MIRA und den Modellserver beenden"),
        @("MIRA prüfen", "verify.cmd", "Tests und NPU-Prüfung"),
        @("MIRA NPU-Demo", "npu-demo.cmd", "30 s Antworten auf der NPU, im Task-Manager sichtbar"))) {
    $lnk = $shell.CreateShortcut("$menu\$($l[0]).lnk")
    if ($l[1] -like "*.ps1") { $lnk.TargetPath = $ps; $lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Target\$($l[1])`"" }
    else { $lnk.TargetPath = "$env:SystemRoot\System32\cmd.exe"; $lnk.Arguments = "/k `"`"$Target\$($l[1])`"`"" }
    $lnk.WorkingDirectory = $Target
    $lnk.Description = $l[2]
    $lnk.Save()
}
Write-Host "Done. Start menu > MIRA > 'MIRA Wartungsassistent'. Check this machine: $Target\verify.cmd"
if ($Start) { & "$Target\Start-MIRA.ps1" }

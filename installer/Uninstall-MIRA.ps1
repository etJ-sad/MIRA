<#
.SYNOPSIS
  Removes a MIRA installation and its Start menu entries. Documents, index and logs in %LOCALAPPDATA%\MIRA are
  kept unless -RemoveUserData is given.
#>
param([string]$Target = "$env:LOCALAPPDATA\Programs\MIRA", [switch]$RemoveUserData)
$ErrorActionPreference = "Stop"
if (Test-Path "$Target\Stop-MIRA.ps1") { & "$Target\Stop-MIRA.ps1" }
if (Test-Path "$Target\runtime\python\python.exe") { Remove-Item -Recurse -Force $Target }
Remove-Item -Recurse -Force (Join-Path ([Environment]::GetFolderPath("Programs")) "MIRA") -ErrorAction SilentlyContinue
if ($RemoveUserData) { Remove-Item -Recurse -Force "$env:LOCALAPPDATA\MIRA" -ErrorAction SilentlyContinue }
Write-Host "MIRA removed."

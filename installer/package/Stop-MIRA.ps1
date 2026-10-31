<#
.SYNOPSIS
  Stops MIRA and the model server started from this folder.
#>
$here = $PSScriptRoot
Get-Process python, ovms -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$here\*" } | Stop-Process -Force
Write-Host "MIRA stopped."

# Startet OpenVINO Model Server mit LLM und Embeddings auf der NPU (Port 8000).
param(
    [string]$Ovms = ".\ovms\ovms.exe",
    [string]$Models = ".\models",
    [int]$Port = 8000
)
Set-Location (Resolve-Path "$PSScriptRoot\..")
$setupvars = Join-Path (Split-Path $Ovms) "setupvars.ps1"
if (Test-Path $setupvars) { . $setupvars | Out-Null }
& $Ovms --rest_port $Port --config_path (Join-Path $Models "config.json")

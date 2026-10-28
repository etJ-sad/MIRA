# Startet OpenVINO Model Server mit LLM und Embeddings auf der NPU (Port 8000).
param(
    [string]$Ovms = ".\ovms\ovms.exe",
    [string]$Models = ".\models",
    [int]$Port = 8000
)
& $Ovms --rest_port $Port --config_path (Join-Path $Models "config.json")

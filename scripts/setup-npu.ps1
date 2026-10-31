# Lädt LLM und Embedding-Modell für die NPU und trägt beide in models\config.json ein.
# Voraussetzung: Intel NPU-Treiber installiert. Fehlt ovms\ovms.exe, wird OVMS vorher geladen (scripts\get-ovms.ps1).
param(
    [string]$Ovms = ".\ovms\ovms.exe",
    [string]$Models = ".\models",
    [string]$LlmModel = "OpenVINO/Qwen3-8B-int4-cw-ov",
    [string]$EmbedModel = "OpenVINO/Qwen3-Embedding-0.6B-int8-ov",
    [int]$MaxPromptLen = 4000
)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..")
if (-not (Test-Path $Ovms)) { & "$PSScriptRoot\get-ovms.ps1" -Target (Split-Path $Ovms) }
$setupvars = Join-Path (Split-Path $Ovms) "setupvars.ps1"
if (Test-Path $setupvars) { . $setupvars | Out-Null }
New-Item -ItemType Directory -Force -Path $Models | Out-Null
$config = Join-Path $Models "config.json"

& $Ovms --pull --source_model $LlmModel --model_repository_path $Models --target_device NPU --task text_generation `
    --cache_dir .ov_cache --enable_prefix_caching true --max_prompt_len $MaxPromptLen
& $Ovms --add_to_config --config_path $config --model_name $LlmModel --model_path $LlmModel

& $Ovms --pull --source_model $EmbedModel --model_repository_path $Models --target_device NPU --task embeddings `
    --pooling LAST --max_length 1000
& $Ovms --add_to_config --config_path $config --model_name $EmbedModel --model_path $EmbedModel

Write-Host "Fertig. Server starten mit: .\scripts\start-ovms.ps1"

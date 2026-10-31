<#
.SYNOPSIS
  Starts MIRA: the OpenVINO Model Server with both models on the NPU (port 8000), then MIRA's web UI and API
  (port 8080), and opens the browser. Whatever is already running is reused. Stop with Stop-MIRA.ps1.
  Documents, index and logs: %LOCALAPPDATA%\MIRA (logs\ovms.log, logs\mira.log).
.PARAMETER Network
  Listen on all interfaces, so tablets and the HMI can open MIRA (Windows Firewall asks once). Default: this PC only.
.PARAMETER OvmsOnly
  Start only the model server (used by verify.cmd and npu-demo.cmd).
#>
param([int]$Port = 8080, [int]$OvmsPort = 8000, [switch]$Network, [switch]$NoBrowser, [switch]$OvmsOnly)
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$data = "$env:LOCALAPPDATA\MIRA"
New-Item -ItemType Directory -Force "$data\logs" | Out-Null
$env:MIRA_DATA_DIR = $data
$env:MIRA_MODELS = "$here\models"
$env:MIRA_SAMPLES = "$here\samples\fz-300"
$env:MIRA_OVMS_URL = "http://localhost:$OvmsPort/v3"

function Get-Json($url) { try { Invoke-RestMethod $url -TimeoutSec 3 } catch { $null } }
function Wait-Models {
    $cfg = Get-Json "http://localhost:$OvmsPort/v1/config"
    $cfg -and $cfg.PSObject.Properties.Count -ge 2 -and -not ($cfg.PSObject.Properties.Value.model_version_status.state | Where-Object { $_ -ne "AVAILABLE" })
}

if (-not (Wait-Models)) {
    if (-not (Get-Json "http://localhost:$OvmsPort/v1/config")) {
        Write-Host "Starting the model server: LLM and embeddings are compiled for the NPU (first start: several minutes)"
        if (Test-Path "$here\ovms\setupvars.ps1") { . "$here\ovms\setupvars.ps1" | Out-Null }
        $ovmsArgs = "--rest_port $OvmsPort --config_path `"$here\models\config.json`" --cache_dir `"$data\ov_cache`""
        $script:ovms = Start-Process "$here\ovms\ovms.exe" -ArgumentList $ovmsArgs -WorkingDirectory "$here\models" -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput "$data\logs\ovms.log" -RedirectStandardError "$data\logs\ovms.err.log"
    }
    $t0 = Get-Date
    while (-not (Wait-Models)) {
        if ($script:ovms -and $script:ovms.HasExited) {
            Get-Content "$data\logs\ovms.log", "$data\logs\ovms.err.log" -Tail 20 -ErrorAction SilentlyContinue
            throw "The model server stopped. Is the Intel NPU driver installed? Log: $data\logs\ovms.log"
        }
        if (((Get-Date) - $t0).TotalMinutes -gt 20) { throw "Models not AVAILABLE after 20 minutes. Log: $data\logs\ovms.log" }
        Write-Host ("   loading onto the NPU ... {0:N0} s" -f ((Get-Date) - $t0).TotalSeconds)
        Start-Sleep 5
    }
}
Write-Host "Model server ready: both models AVAILABLE on the NPU (http://localhost:$OvmsPort)"
if ($OvmsOnly) { return }

$url = "http://localhost:$Port"
if (-not (Get-Json "$url/api/health")) {
    $bind = if ($Network) { "0.0.0.0" } else { "127.0.0.1" }
    Start-Process "$here\runtime\python\python.exe" -ArgumentList "-I -m mira.cli serve --host $bind --port $Port" -WorkingDirectory $data `
        -WindowStyle Hidden -RedirectStandardOutput "$data\logs\mira.log" -RedirectStandardError "$data\logs\mira.err.log" | Out-Null
    $t0 = Get-Date
    while (-not (Get-Json "$url/api/health")) {
        if (((Get-Date) - $t0).TotalSeconds -gt 60) { throw "MIRA did not start. Log: $data\logs\mira.err.log" }
        Start-Sleep 1
    }
}
Write-Host "MIRA is running: $url"
if ($Network) { Write-Host "From a tablet or the HMI: http://$($env:COMPUTERNAME):$Port" }
if (-not $NoBrowser) { Start-Process $url }

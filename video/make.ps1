<#
.SYNOPSIS
  Rebuilds the MIRA story videos: real MIRA results on the NPU -> narration -> timing -> voice processing, music and mix -> frames -> MP4.
    eco   video\mira-story-ecosystem.mp4   the shared NPU story, ends with Lumen, MIRA and Greenforest (script.json)
    solo  video\mira-story-standalone.mp4  MIRA on its own, own wording, voice and chapters (script-solo.json)
  Both cuts use the same measurement (one assets.py run).
  Needs the NPU and OVMS with both MIRA models (scripts\setup-npu.ps1 once), and a build venv for the video tools:
    py -3.12 -m venv build\video-venv; build\video-venv\Scripts\pip install -e . playwright kokoro-onnx soundfile imageio-ffmpeg numpy psutil reportlab pypdfium2 openvino-genai
  OVMS is started here when it is not running yet. Rendering uses the installed Edge or Chrome. About 10 minutes per cut
  (the speech model download adds ~340 MB on the first run).
  -Preview: no NPU needed, simulated models; every frame is marked as placeholder numbers.
#>
param([string]$Work = "$PSScriptRoot\work", [string]$Ovms = ".\ovms\ovms.exe", [string]$Models = ".\models", [switch]$Preview, [ValidateSet("eco", "solo", "both")][string]$Variant = "both", [switch]$SkipAssets, [switch]$NoRender)
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
Set-Location $root
$tools = "$PSScriptRoot\tools"
$vpy = "$root\build\video-venv\Scripts\python.exe"
$ff = & $vpy -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
$m = "$Work\models"; New-Item -ItemType Directory -Force $m | Out-Null
$rel = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
foreach ($f in "kokoro-v1.0.onnx", "voices-v1.0.bin") { if (-not (Test-Path "$m\$f")) { curl.exe -fL --retry 4 -o "$m\$f" "$rel/$f" } }
if (-not (Test-Path "$PSScriptRoot\demo\docs")) { & $vpy "$PSScriptRoot\demo\make_docs.py" "$PSScriptRoot\demo\docs" }

$ovmsProc = $null
if ($SkipAssets) {
    Write-Host "using the measurement in $Work\assets.json"
} elseif ($Preview) {
    Write-Host "PREVIEW: simulated models, placeholder numbers"; & $vpy "$tools\assets.py" $Work --preview
} else {
    $up = $false; try { Invoke-RestMethod http://localhost:8000/v1/config -TimeoutSec 3 | Out-Null; $up = $true } catch { }
    if (-not $up) {
        Write-Host "starting OVMS (models load onto the NPU, can take a few minutes)"
        $ovmsProc = Start-Process $Ovms -ArgumentList "--rest_port 8000 --config_path `"$(Join-Path $Models 'config.json')`"" -PassThru -WindowStyle Minimized
        do { Start-Sleep 5; $cfg = try { Invoke-RestMethod http://localhost:8000/v1/config -TimeoutSec 3 } catch { $null } }
        until ($cfg -and -not ($cfg.PSObject.Properties.Value.model_version_status.state | Where-Object { $_ -ne "AVAILABLE" }))
    }
    $env:OVMS_VERSION = (& $Ovms --version | Select-Object -First 1)
    $env:MIRA_MODELS = (Resolve-Path $Models)
    Write-Host "real results on the NPU"; & $vpy "$tools\assets.py" $Work
}
$logo = if ($env:MIRA_LOGO) { $env:MIRA_LOGO } elseif (Test-Path "C:\Kassia\webui\shared\assets\branding\logos\sie-logo-petrol-rgb.png") { "C:\Kassia\webui\shared\assets\branding\logos\sie-logo-petrol-rgb.png" } else { "-" }
$music = Get-ChildItem "$PSScriptRoot\music.*" -ErrorAction SilentlyContinue | Select-Object -First 1
$cuts = if ($Variant -eq "both") { "eco", "solo" } else { , $Variant }
foreach ($v in $cuts) {
    $env:MIRA_VARIANT = $v
    $W = "$Work\$v"; New-Item -ItemType Directory -Force "$W\voice" | Out-Null
    $name = "mira-story-$(if ($v -eq 'eco') { 'ecosystem' } else { 'standalone' })"
    $out = if ($Preview) { "$Work\$name-preview.mp4" } else { "$PSScriptRoot\$name.mp4" }
    Write-Host "[$v] 1/5 narration";         & $vpy "$tools\voice.py" $m "$W\voice"
    Write-Host "[$v] 2/5 scene timing";      & $vpy "$tools\build.py" $W; & $vpy "$tools\render.py" starts "$W\render.html" "$W\starts.json"
    Write-Host "[$v] 3/5 voice processing, music and mix"
    & $vpy "$tools\mix.py" $W voice
    # broadcast chain: rumble cut, less mud, presence, air, de-esser, compression, a small room
    & $ff -loglevel error -y -i "$W\voice_raw.wav" -af "highpass=f=80,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3500:t=q:w=1.2:g=2.5,highshelf=f=9000:g=2,deesser,acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=3,aecho=0.8:0.6:28|47:0.08|0.05" -ar 48000 "$W\voice_fx.wav"
    if ($music) { & $ff -loglevel error -y -i $music.FullName -ar 48000 -ac 2 "$W\music_ext.wav" } else { Remove-Item "$W\music_ext.wav" -ErrorAction SilentlyContinue }
    & $vpy "$tools\mix.py" $W final
    & $ff -loglevel error -y -i "$W\mix_raw.wav" -af "loudnorm=I=-16:TP=-1.5:LRA=9" -ar 48000 -ac 2 "$W\mix.wav"
    & $ff -loglevel error -y -i "$W\mix.wav" -b:a 192k "$W\mix.mp3"
    Write-Host "[$v] 4/5 pages";             & $vpy "$tools\build.py" $W "$W\mix.mp3" "$W\amp.json"
    if ($NoRender) { continue }
    Write-Host "[$v] 5/5 video";             & $vpy "$tools\render.py" video "$W\render.html" $out "$W\mix.wav" $logo
    Write-Host "done: $out"
}
Remove-Item Env:MIRA_VARIANT
if ($ovmsProc) { Stop-Process $ovmsProc -ErrorAction SilentlyContinue }

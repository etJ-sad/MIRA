<#
.SYNOPSIS
  Builds the offline MIRA package, like Lumen's: embedded Python + MIRA + OpenVINO Model Server + both NPU models
  + demo documents. Output: build\release\MIRA\ (installable folder) and build\release\MIRA-<version>-win-x64.zip.

  Needs, once, on the build machine:
    ovms\ovms.exe        the OVMS package for Windows, extracted
    models\config.json   both models pulled for the NPU (scripts\setup-npu.ps1)
  and internet for the python.org embeddable zip and the PyPI wheels. The result needs no internet.
#>
param(
    [string]$PythonVersion = "3.14.7",
    [string]$PythonEmbedSha256 = "d297e5ff019966817ad8502465176139f2d3d840fa4ed84b13bed399a6ab1f15",  # python.org 3.14.7 embed-amd64
    [string]$Ovms = ".\ovms",
    [string]$Models = ".\models",
    [switch]$NoZip
)
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
Set-Location $root
$version = (Select-String -Path "$root\pyproject.toml" -Pattern '^version = "(.+)"').Matches[0].Groups[1].Value
$out = "$root\build\release"
$dist = "$out\MIRA"
$cache = "$root\build\cache"
New-Item -ItemType Directory -Force $out, $cache | Out-Null
if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
New-Item -ItemType Directory -Force $dist | Out-Null
$bpy = if (Test-Path "$root\.venv\Scripts\python.exe") { "$root\.venv\Scripts\python.exe" } else { (Get-Command py).Source }

Write-Host "== 1/7 model server and models"
if (-not (Test-Path "$Ovms\ovms.exe")) { throw "OVMS not found at $Ovms\ovms.exe. Extract the OVMS Windows package there." }
if (-not (Test-Path "$Models\config.json")) { throw "No $Models\config.json. Run .\scripts\setup-npu.ps1 first." }
$cfg = Get-Content "$Models\config.json" -Raw | ConvertFrom-Json
foreach ($m in @(@($cfg.mediapipe_config_list) + @($cfg.model_config_list) | Where-Object { $_ })) {
    $name = if ($m.name) { $m.name } else { $m.config.name }
    $graph = Get-ChildItem "$Models\$name" -Recurse -Filter graph.pbtxt -ErrorAction SilentlyContinue | Select-Object -First 1
    $dev = if ($graph) { (Select-String -Path $graph.FullName -Pattern 'device:\s*"([^"]+)"').Matches | ForEach-Object { $_.Groups[1].Value } | Select-Object -First 1 }
    Write-Host "   $name -> $dev"
    if ($dev -and $dev -ne "NPU") { throw "$name is compiled for $dev, not the NPU. Re-run scripts\setup-npu.ps1." }
}
$ovmsVersion = (& "$Ovms\ovms.exe" --version | Select-Object -First 1)
Write-Host "   $ovmsVersion"

Write-Host "== 2/7 embedded Python $PythonVersion"
$zip = "$cache\python-$PythonVersion-embed-amd64.zip"
if (-not (Test-Path $zip)) {
    curl.exe -sS --fail --retry 4 -o $zip "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
    if ($LASTEXITCODE) { throw "python download failed" }
}
$sha = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
if ($PythonEmbedSha256 -and $sha -ne $PythonEmbedSha256.ToLower()) { throw "python embeddable checksum mismatch: $sha" }
$py = "$dist\runtime\python"
Expand-Archive $zip -DestinationPath $py
$tag = ($PythonVersion.Split('.')[0..1] -join '')
# ._pth: isolated path list (no user site, no PYTHONPATH); app code and packages are explicit.
@("python$tag.zip", ".", "site-packages", "..\app") | Set-Content -Encoding ascii "$py\python$tag._pth"

Write-Host "== 3/7 runtime wheels (binary only, from pyproject.toml, plus pytest and psutil for verify.cmd)"
$deps = & $bpy -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))"
& $bpy -m pip install --quiet --only-binary=:all: --platform win_amd64 --python-version $tag `
    --implementation cp --target "$py\site-packages" @deps "pytest" "psutil"
if ($LASTEXITCODE) { throw "pip install failed" }
Remove-Item -Recurse -Force "$py\site-packages\bin" -ErrorAction SilentlyContinue
& $bpy -m pip freeze --path "$py\site-packages" | Set-Content "$dist\runtime\requirements.lock.txt"
Get-ChildItem "$py\site-packages" -Directory -Filter *.dist-info | ForEach-Object {
    $lic = Get-ChildItem $_.FullName -Recurse -File | Where-Object { $_.Name -match '^(LICEN[CS]E|COPYING|NOTICE)' }
    if ($lic) {
        $d = "$dist\LICENSES\python-packages\$($_.Name -replace '\.dist-info$','')"
        New-Item -ItemType Directory -Force $d | Out-Null
        $lic | Copy-Item -Destination $d
    }
}

Write-Host "== 4/7 MIRA, unit tests, demo documents, scripts"
New-Item -ItemType Directory -Force "$dist\runtime\app\tests" | Out-Null
Copy-Item -Recurse "$root\mira" "$dist\runtime\app\mira"
Copy-Item "$root\tests\*.py" "$dist\runtime\app\tests"
Get-ChildItem -Recurse -Directory "$dist\runtime\app" -Filter __pycache__ | Remove-Item -Recurse -Force
New-Item -ItemType Directory -Force "$dist\samples", "$dist\docs" | Out-Null
Copy-Item -Recurse "$root\samples\fz-300" "$dist\samples\fz-300"
Copy-Item "$root\docs\*.md" "$dist\docs"
Copy-Item "$root\README.md" "$dist\"
Copy-Item "$PSScriptRoot\package\*" "$dist\"
Copy-Item "$PSScriptRoot\Install-MIRA.ps1", "$PSScriptRoot\Uninstall-MIRA.ps1" "$dist\"

Write-Host "== 5/7 OVMS and models (several GB)"
robocopy $Ovms "$dist\ovms" /E /NFL /NDL /NJH /NJS /NP | Out-Null
robocopy $Models "$dist\models" /E /XD .ov_cache /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "copying the models failed" }
$global:LASTEXITCODE = 0
@{ version = $version; ovms = "$ovmsVersion"; python = $PythonVersion; built = (Get-Date -Format s) } | ConvertTo-Json | Set-Content "$dist\version.json"

Write-Host "== 6/7 smoke test of the bundled runtime (no repo, no venv, isolated)"
& "$py\python.exe" -I -c "import mira, mira.app, mira.check, qdrant_client, fastapi; print('runtime ok, MIRA', mira.__version__)"
if ($LASTEXITCODE) { throw "bundled runtime smoke test failed" }
& "$py\python.exe" -I -m pytest -q -p no:cacheprovider "$dist\runtime\app\tests"
if ($LASTEXITCODE) { throw "unit tests failed in the bundled runtime" }

if ($NoZip) { Write-Host "folder: $dist"; return }
Write-Host "== 7/7 zip"
$z = "$out\MIRA-$version-win-x64.zip"
if (Test-Path $z) { Remove-Item $z }
# tar.exe (bsdtar, part of Windows) writes zip64, Compress-Archive stops at 2 GB
tar.exe -a -c -f $z -C $out MIRA
if ($LASTEXITCODE) { throw "zip failed" }
(Get-FileHash $z -Algorithm SHA256).Hash | Set-Content "$z.sha256"
Write-Host ("package: $z ({0:N1} GB)" -f ((Get-Item $z).Length / 1GB))

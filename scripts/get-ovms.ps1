<#
.SYNOPSIS
  Downloads the OpenVINO Model Server package for Windows from GitHub and extracts it to .\ovms (ovms\ovms.exe).
  Default: the latest release. -Version v2025.4 (a release tag) pins one. -Url takes a zip you picked yourself.
#>
param([string]$Version = "latest", [string]$Url, [string]$Target = ".\ovms")
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest is many times faster without the progress bar
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
if (Test-Path "$Target\ovms.exe") { Write-Host "OVMS already in $Target"; & "$Target\ovms.exe" --version; return }

if (-not $Url) {
    $api = if ($Version -eq "latest") { "https://api.github.com/repos/openvinotoolkit/model_server/releases/latest" }
           else { "https://api.github.com/repos/openvinotoolkit/model_server/releases/tags/$Version" }
    $release = Invoke-RestMethod $api -Headers @{ "User-Agent" = "MIRA-setup" }
    $zips = $release.assets | Where-Object { $_.name -match 'windows' -and $_.name -like '*.zip' }
    # the package with Python support is the documented default; fall back to any Windows zip
    $asset = ($zips | Where-Object { $_.name -match 'python_on' } | Select-Object -First 1), ($zips | Select-Object -First 1) |
        Where-Object { $_ } | Select-Object -First 1
    if (-not $asset) {
        throw "No Windows zip in OVMS release $($release.tag_name). Pick one at https://github.com/openvinotoolkit/model_server/releases and run: .\scripts\get-ovms.ps1 -Url <zip url>"
    }
    $Url = $asset.browser_download_url
    Write-Host "OVMS $($release.tag_name): $($asset.name) ($([math]::Round($asset.size / 1MB)) MB)"
}
$tmp = Join-Path $env:TEMP "mira-ovms"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
New-Item -ItemType Directory -Force $tmp | Out-Null
Write-Host "downloading $Url"
Invoke-WebRequest $Url -OutFile "$tmp\ovms.zip" -UseBasicParsing
Write-Host "extracting"
tar.exe -xf "$tmp\ovms.zip" -C $tmp
if ($LASTEXITCODE) { Expand-Archive "$tmp\ovms.zip" -DestinationPath $tmp -Force }
$exe = Get-ChildItem $tmp -Recurse -Filter ovms.exe | Select-Object -First 1
if (-not $exe) { throw "ovms.exe not found in the downloaded package." }
Move-Item $exe.DirectoryName $Target
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
if (Test-Path "$Target\setupvars.ps1") { . "$Target\setupvars.ps1" | Out-Null }
& "$Target\ovms.exe" --version
Write-Host "OVMS ready: $Target\ovms.exe"

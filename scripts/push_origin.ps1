# Push master and mirror to main (backup if CI sync is delayed).
param(
    [switch]$MasterOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

git push origin master
if ($LASTEXITCODE -ne 0) { exit 1 }

if (-not $MasterOnly) {
    git push origin master:main
    if ($LASTEXITCODE -ne 0) { exit 1 }
    Write-Host "Pushed master + synced main" -ForegroundColor Green
} else {
    Write-Host "Pushed master only (main sync via GitHub Action)" -ForegroundColor Green
}

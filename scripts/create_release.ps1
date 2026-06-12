# Create or update GitHub Release for v1.2.0-industrial
# Run from repo ROOT: C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate

$ErrorActionPreference = "Stop"
$Gh = "C:\Program Files\GitHub CLI\gh.exe"

if (-not (Test-Path $Gh)) {
    Write-Host "GitHub CLI not found. Install: winget install GitHub.cli" -ForegroundColor Red
    exit 1
}

$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$Tag = "v1.2.0-industrial"
$Notes = Join-Path $Root "RELEASE_NOTES_v1.2.0-industrial.md"
if (-not (Test-Path $Notes)) {
    Write-Host "Missing: $Notes" -ForegroundColor Red
    exit 1
}

$env:Path = "$env:Path;C:\Program Files\GitHub CLI"

Write-Host "Repo: $Root" -ForegroundColor Cyan
& $Gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Login first (browser will open):" -ForegroundColor Yellow
    Write-Host "  & `"$Gh`" auth login" -ForegroundColor White
    exit 1
}

$existing = & $Gh release view $Tag --repo "Gruver87/absolute-blockchain-ultimate" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "Updating release $Tag ..." -ForegroundColor Cyan
    & $Gh release edit $Tag `
        --title "v1.2.0-industrial - Industrial Educational Node" `
        --notes-file $Notes `
        --latest `
        --prerelease=false `
        --repo "Gruver87/absolute-blockchain-ultimate"
} else {
    Write-Host "Creating release $Tag ..." -ForegroundColor Cyan
    & $Gh release create $Tag `
        --title "v1.2.0-industrial - Industrial Educational Node" `
        --notes-file $Notes `
        --latest `
        --repo "Gruver87/absolute-blockchain-ultimate"
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "Release ready: https://github.com/Gruver87/absolute-blockchain-ultimate/releases/tag/$Tag" -ForegroundColor Green
}

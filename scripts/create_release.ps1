# Create GitHub Release for v1.0-educational
# Run from repo ROOT: C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate

$ErrorActionPreference = "Stop"
$Gh = "C:\Program Files\GitHub CLI\gh.exe"

if (-not (Test-Path $Gh)) {
    Write-Host "GitHub CLI not found. Install: winget install GitHub.cli" -ForegroundColor Red
    exit 1
}

$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$Notes = Join-Path $Root "RELEASE_NOTES_v1.0-educational.md"
if (-not (Test-Path $Notes)) {
    Write-Host "Missing: $Notes" -ForegroundColor Red
    exit 1
}

# Add gh to PATH for this session
$env:Path = "$env:Path;C:\Program Files\GitHub CLI"

Write-Host "Repo: $Root" -ForegroundColor Cyan
& $Gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Login first (browser will open):" -ForegroundColor Yellow
    Write-Host "  & `"$Gh`" auth login" -ForegroundColor White
    exit 1
}

& $Gh release create "v1.0-educational" `
    --title "v1.0-educational - Unified Educational Node" `
    --notes-file $Notes `
    --prerelease `
    --repo "Gruver87/absolute-blockchain-ultimate"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Release created: https://github.com/Gruver87/absolute-blockchain-ultimate/releases/tag/v1.0-educational" -ForegroundColor Green
}

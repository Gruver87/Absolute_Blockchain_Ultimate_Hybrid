# Add GitHub CLI to PATH (current PowerShell session + user PATH permanently)
$GhDir = "C:\Program Files\GitHub CLI"
$Gh = Join-Path $GhDir "gh.exe"

if (-not (Test-Path $Gh)) {
    Write-Host "Install GitHub CLI: winget install GitHub.cli" -ForegroundColor Red
    exit 1
}

$env:Path = "$env:Path;$GhDir"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*GitHub CLI*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$GhDir", "User")
    Write-Host "Added GitHub CLI to user PATH. Restart terminal after this." -ForegroundColor Green
}

& $Gh --version
Write-Host ""
Write-Host "Next: gh auth login" -ForegroundColor Yellow

# Add GitHub CLI to PATH and ensure authentication
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
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

# Already logged in via gh keyring / prior auth?
$status = & $Gh auth status 2>&1 | Out-String
if ($LASTEXITCODE -eq 0 -and $status -match "Logged in") {
    Write-Host "gh already authenticated (keyring or prior login):" -ForegroundColor Green
    Write-Host $status.Trim()
    Write-Host ""
    Write-Host "Push:  git push origin master" -ForegroundColor Yellow
    Write-Host "PR:    gh pr create" -ForegroundColor Yellow
    exit 0
}

# Try token from local .env only when gh is not logged in
$EnvFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Host "Not logged in. Create .env and run:" -ForegroundColor Yellow
    Write-Host "  .\scripts\set_github_token.ps1 -Token ghp_..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Classic PAT scopes required: repo, read:org" -ForegroundColor Gray
    exit 1
}

$tokenLine = Get-Content $EnvFile -Encoding UTF8 |
    Where-Object { $_ -match '^\s*GITHUB_TOKEN\s*=\s*(.+)\s*$' } |
    Select-Object -First 1

if (-not $tokenLine -or $tokenLine -notmatch '=\s*(.+)$' -or -not $Matches[1] -or $Matches[1] -match '^(your_|$)') {
    Write-Host "GITHUB_TOKEN missing in .env" -ForegroundColor Red
    Write-Host "  .\scripts\set_github_token.ps1 -Token ghp_..." -ForegroundColor Yellow
    exit 1
}

$token = $Matches[1].Trim()
$token | & $Gh auth login --with-token
if ($LASTEXITCODE -eq 0) {
    Write-Host "gh authenticated from .env GITHUB_TOKEN" -ForegroundColor Green
    & $Gh auth status
    exit 0
}

Write-Host "Token from .env rejected by GitHub CLI." -ForegroundColor Red
Write-Host "Classic PAT needs scopes: repo, read:org (Settings -> Developer settings -> Personal access tokens -> Tokens classic)." -ForegroundColor Yellow
Write-Host "Or login interactively:  gh auth login" -ForegroundColor Yellow
exit 1

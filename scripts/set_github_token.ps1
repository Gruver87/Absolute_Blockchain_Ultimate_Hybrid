# Set GITHUB_TOKEN in local .env (gitignored). Usage:
#   .\scripts\set_github_token.ps1 -Token "ghp_..."
param(
    [Parameter(Mandatory = $true)]
    [string]$Token
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$EnvPath = Join-Path $ProjectRoot ".env"

if (-not (Test-Path $EnvPath)) {
    Copy-Item (Join-Path $ProjectRoot ".env.example") $EnvPath
}

$lines = Get-Content $EnvPath -Encoding UTF8
$found = $false
$newLines = foreach ($line in $lines) {
    if ($line -match '^\s*GITHUB_TOKEN\s*=') {
        $found = $true
        "GITHUB_TOKEN=$Token"
    }
    else {
        $line
    }
}
if (-not $found) {
    $newLines += "GITHUB_TOKEN=$Token"
}
Set-Content -Path $EnvPath -Value $newLines -Encoding UTF8

$env:GITHUB_TOKEN = $Token
$env:GH_TOKEN = $Token
Write-Host "GITHUB_TOKEN saved to .env (gitignored)" -ForegroundColor Green
Write-Host "Session env: GITHUB_TOKEN and GH_TOKEN set for this shell" -ForegroundColor Gray

if (Get-Command gh -ErrorAction SilentlyContinue) {
    $ghExe = "gh"
}
elseif (Test-Path "C:\Program Files\GitHub CLI\gh.exe") {
    $ghExe = "C:\Program Files\GitHub CLI\gh.exe"
}
else {
    $ghExe = $null
}

if ($ghExe) {
    $Token | & $ghExe auth login --with-token 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "gh CLI authenticated" -ForegroundColor Green
    }
    else {
        Write-Host "gh auth failed - run: .\scripts\setup_gh.ps1" -ForegroundColor Yellow
    }
}
else {
    Write-Host "gh not found - install: winget install GitHub.cli" -ForegroundColor Yellow
}

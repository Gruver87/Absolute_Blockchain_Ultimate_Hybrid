# Create .env from .env.example if missing (never overwrites existing .env)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$envFile = Join-Path $ProjectRoot ".env"
$example = Join-Path $ProjectRoot ".env.example"

if (Test-Path $envFile) {
    Write-Host ".env already exists - not modified" -ForegroundColor Green
    exit 0
}

if (-not (Test-Path $example)) {
    Write-Host "Missing .env.example" -ForegroundColor Red
    exit 1
}

Copy-Item $example $envFile
Write-Host "Created .env from .env.example" -ForegroundColor Green
Write-Host "Edit .env locally, then run: python scripts/apply_local_secrets.py" -ForegroundColor Yellow

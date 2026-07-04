# Pin GENESIS_CEREMONY_HASH from a generated ceremony directory (never commit keys).
param(
    [string]$CeremonyDir = "data/ceremony_keys",
    [switch]$StrictMainnet
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$manifest = Join-Path $CeremonyDir "validators.manifest.json"
if (-not (Test-Path $manifest)) {
    Write-Host "FAIL: missing $manifest - run: python scripts/genesis_ceremony_keygen.py" -ForegroundColor Red
    exit 1
}

$pyArgs = @(
    "scripts/genesis_ceremony.py",
    "--config", "node.prod.mainnet-v1.example.json",
    "--manifest", $manifest,
    "--json"
)
if ($StrictMainnet) { $pyArgs += "--strict-mainnet" }

$json = python @pyArgs | ConvertFrom-Json
if ($json.errors -and $json.errors.Count -gt 0) {
    Write-Host "FAIL: ceremony errors:" -ForegroundColor Red
    $json.errors | ForEach-Object { Write-Host "  - $_" }
    exit 1
}

$hash = $json.ceremony_hash
$env:GENESIS_CEREMONY_HASH = $hash
Write-Host "OK: GENESIS_CEREMONY_HASH pinned for this session" -ForegroundColor Green
Write-Host "  $hash"
Write-Host ""
Write-Host "Persist in deploy shell / docker-compose:"
Write-Host ('  $env:GENESIS_CEREMONY_HASH = "' + $hash + '"')

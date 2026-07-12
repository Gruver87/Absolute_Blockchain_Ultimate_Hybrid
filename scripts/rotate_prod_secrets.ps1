# Rotate production secrets in .env without changing ceremony pin or chain_id.
param(
    [switch]$Force,
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$envPath = Join-Path $Root $EnvFile
if (-not (Test-Path $envPath)) {
    Write-Host "FAIL: $EnvFile not found — run .\scripts\setup_prod_env.ps1 first" -ForegroundColor Red
    exit 1
}

function New-Secret([int]$Bytes = 32) {
    $buf = New-Object byte[] $Bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buf)
    return [Convert]::ToBase64String($buf).TrimEnd("=").Replace("+", "x").Replace("/", "y")
}

$preserve = @(
    "CHAIN_ID",
    "GENESIS_CEREMONY_HASH",
    "VALIDATORS_MANIFEST_PATH",
    "ETH_RPC_URL",
    "CORS_ORIGINS",
    "DEPLOYMENT_MODE",
    "BRIDGE_ENABLED",
    "BRIDGE_MODE",
    "BRIDGE_PROBE_L1_RPC",
    "BRIDGE_REQUIRE_L1_PROOF",
    "ABS_REQUIRE_NATIVE_CRYPTO",
    "RPC_API_KEY_REQUIRED"
)

$existing = @{}
Get-Content $envPath | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { return }
    $parts = $line.Split("=", 2)
    $existing[$parts[0].Trim()] = $parts[1].Trim().Trim('"').Trim("'")
}

if (-not $Force) {
    Write-Host "This will rotate JWT_SECRET, RPC_API_KEYS, BRIDGE_ORACLE_SECRET in $EnvFile" -ForegroundColor Yellow
    Write-Host "Preserved: $($preserve -join ', ')" -ForegroundColor DarkGray
    Write-Host "Re-run with -Force to apply." -ForegroundColor Yellow
    exit 0
}

$backup = "$envPath.bak.$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item $envPath $backup
Write-Host "Backup: $backup" -ForegroundColor DarkGray

Push-Location $Root
try {
    $rpcKey = (python -c "from middleware.rpc_auth import RPCApiKeyAuth; print(RPCApiKeyAuth.generate_key())").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $rpcKey) { throw "RPC key generation failed" }
} finally {
    Pop-Location
}

$existing["JWT_SECRET"] = New-Secret 32
$existing["BRIDGE_ORACLE_SECRET"] = New-Secret 32
$existing["RPC_API_KEYS"] = $rpcKey

$lines = @("# Rotated by scripts/rotate_prod_secrets.ps1 $(Get-Date -Format o)")
foreach ($key in ($existing.Keys | Sort-Object)) {
    $lines += "$key=$($existing[$key])"
}
Set-Content -Path $envPath -Value $lines -Encoding UTF8

Write-Host "OK: secrets rotated in $EnvFile" -ForegroundColor Green
Write-Host "  Restart all prod nodes / docker compose to pick up new JWT and RPC keys." -ForegroundColor Cyan
Write-Host "  Update client RPC key; invalidate old sessions." -ForegroundColor Cyan
Write-Host ""
Write-Host "New RPC key:" -ForegroundColor Gray
Write-Host "  $rpcKey" -ForegroundColor Gray

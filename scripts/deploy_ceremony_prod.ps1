# Copy ceremony manifest + wallet into data/ and pin GENESIS_CEREMONY_HASH.
param(
    [string]$CeremonyDir = "data/ceremony_keys",
    [int]$ValidatorIndex = 1
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
. "$ProjectRoot\scripts\ceremony_env.ps1"

python scripts/deploy_ceremony_prod.py --ceremony-dir $CeremonyDir --validator-index $ValidatorIndex
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$metaPath = Join-Path $ProjectRoot "data\ceremony_deploy.json"
if (-not (Test-Path $metaPath)) {
    Write-Host "FAIL: missing data/ceremony_deploy.json" -ForegroundColor Red
    exit 1
}
$meta = Get-Content $metaPath -Raw | ConvertFrom-Json
$env:VALIDATORS_MANIFEST_PATH = "data/validators.manifest.json"
$env:GENESIS_CEREMONY_HASH = $meta.ceremony_hash
Sync-CeremonyDeployEnv -ProjectRoot $ProjectRoot -CeremonyHash $meta.ceremony_hash
Write-Host "OK: VALIDATORS_MANIFEST_PATH and GENESIS_CEREMONY_HASH set for this session (+ .env if present)" -ForegroundColor Green

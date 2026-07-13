# Start 2-node public testnet mesh (seed + validator) and verify sync.
param(
    [switch]$SkipBuild,
    [int]$WaitSec = 120
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

Write-Host "Starting testnet 2-node mesh (seed :19080 + validator :19081)..." -ForegroundColor Cyan
$seedArgs = @("-WithValidator")
if ($SkipBuild) { $seedArgs += "-SkipBuild" }
& (Join-Path $ScriptDir "docker_testnet_seed.ps1") @seedArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Verifying testnet mesh (wait=${WaitSec}s)..." -ForegroundColor Cyan
python (Join-Path $ScriptDir "verify_testnet_mesh.py") --mesh --wait $WaitSec
exit $LASTEXITCODE

# Start 3-node public testnet mesh and verify sync.
param(
    [switch]$SkipBuild,
    [int]$WaitSec = 180
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

Write-Host "Starting testnet 3-node mesh (:19080/:19081/:19082)..." -ForegroundColor Cyan
$seedArgs = @("-Mesh3")
if ($SkipBuild) { $seedArgs += "-SkipBuild" }
& (Join-Path $ScriptDir "docker_testnet_seed.ps1") @seedArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Verifying 3-node mesh (wait=${WaitSec}s)..." -ForegroundColor Cyan
python (Join-Path $ScriptDir "verify_testnet_mesh.py") --mesh3 --wait $WaitSec
exit $LASTEXITCODE

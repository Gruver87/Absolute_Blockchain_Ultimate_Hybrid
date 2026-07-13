# Start prod 3-node mesh with P2P wire TLS overlay.
param(
    [string]$CeremonyDir = "data/ceremony_keys",
    [switch]$SkipBuild,
    [switch]$KeepVolumes,
    [switch]$NoCloneDb,
    [switch]$RecoveryDrill
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

Write-Host "Prod 3-node mesh with P2P TLS..." -ForegroundColor Cyan
$argsList = @("-P2pTls", "-CeremonyDir", $CeremonyDir)
if ($SkipBuild) { $argsList += "-SkipBuild" }
if ($KeepVolumes) { $argsList += "-KeepVolumes" }
if ($NoCloneDb) { $argsList += "-NoCloneDb" }
if ($RecoveryDrill) { $argsList += "-RecoveryDrill" }

& (Join-Path $ScriptDir "docker_prod_3node.ps1") @argsList
exit $LASTEXITCODE

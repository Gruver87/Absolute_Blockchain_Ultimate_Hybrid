# Monolith readiness gate — one command for all static mainnet-prep layers.
param(
    [switch]$StrictAudit,
    [switch]$BridgeCutover,
    [switch]$LiveProdMesh,
    [switch]$P2pCi,
    [string]$CeremonyDir = ""
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$args = @()
if ($StrictAudit) { $args += "--strict-audit" }
if ($BridgeCutover) { $args += "--bridge-cutover" }
if ($LiveProdMesh) { $args += "--live-prod-mesh" }
if ($P2pCi) { $args += "--p2p-ci" }
if ($CeremonyDir) { $args += @("--ceremony-dir", $CeremonyDir) }
$args += "--json"

python (Join-Path $ScriptDir "monolith_gate.py") @args
exit $LASTEXITCODE

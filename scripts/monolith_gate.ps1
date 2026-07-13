# Monolith readiness gate — one command for all static mainnet-prep layers.
param(
    [switch]$StrictAudit,
    [switch]$BridgeCutover,
    [switch]$LiveProdMesh,
    [switch]$P2pCi,
    [switch]$SoakPreflight,
    [switch]$ProbeL1,
    [switch]$ProbeL1RpcOnly,
    [switch]$BridgeLive,
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
if ($SoakPreflight) { $args += "--soak-preflight" }
if ($ProbeL1) { $args += "--probe-l1" }
if ($ProbeL1RpcOnly) { $args += "--probe-l1-rpc-only" }
if ($BridgeLive) { $args += "--bridge-live" }
if ($CeremonyDir) { $args += @("--ceremony-dir", $CeremonyDir) }
$args += "--json"

python (Join-Path $ScriptDir "monolith_gate.py") @args
exit $LASTEXITCODE

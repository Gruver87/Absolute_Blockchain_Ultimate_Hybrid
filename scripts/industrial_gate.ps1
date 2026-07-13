# Industrial code gate (prod stack without external audit blockers)
param(
    [switch]$ProdSmokeSpawn,
    [switch]$BridgeCutover,
    [switch]$ProbeL1,
    [switch]$ProbeL1RpcOnly,
    [switch]$BridgeLive
)

$pyArgs = @()
if ($ProdSmokeSpawn) {
    $pyArgs += "--prod-smoke-spawn"
}
if ($BridgeCutover) { $pyArgs += "--bridge-cutover" }
if ($ProbeL1) { $pyArgs += "--probe-l1" }
if ($ProbeL1RpcOnly) { $pyArgs += "--probe-l1-rpc-only" }
if ($BridgeLive) { $pyArgs += "--bridge-live" }
python "$PSScriptRoot\industrial_gate.py" @pyArgs
exit $LASTEXITCODE

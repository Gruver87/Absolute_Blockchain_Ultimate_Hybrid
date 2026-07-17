# Industrial code gate (prod stack without external audit blockers)
param(
    [switch]$ProdSmokeSpawn,
    [switch]$BridgeCutover,
    [switch]$ProbeL1,
    [switch]$ProbeL1RpcOnly,
    [switch]$BridgeLive,
    [double]$MinSoakHours = 0,
    [string]$CeremonyDir = "",
    [switch]$RequireCeremonyPin,
    [switch]$Json
)

$pyArgs = @()
if ($ProdSmokeSpawn) {
    $pyArgs += "--prod-smoke-spawn"
}
if ($BridgeCutover) { $pyArgs += "--bridge-cutover" }
if ($ProbeL1) { $pyArgs += "--probe-l1" }
if ($ProbeL1RpcOnly) { $pyArgs += "--probe-l1-rpc-only" }
if ($BridgeLive) { $pyArgs += "--bridge-live" }
if ($MinSoakHours -gt 0) {
    $pyArgs += "--min-soak-hours"
    $pyArgs += "$MinSoakHours"
}
if ($CeremonyDir) {
    $pyArgs += "--ceremony-dir"
    $pyArgs += $CeremonyDir
}
if ($RequireCeremonyPin) { $pyArgs += "--require-ceremony-pin" }
if ($Json) { $pyArgs += "--json" }
python "$PSScriptRoot\industrial_gate.py" @pyArgs
exit $LASTEXITCODE

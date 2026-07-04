# Industrial code gate (prod stack without external audit blockers)
param(
    [switch]$ProdSmokeSpawn
)

$pyArgs = @()
if ($ProdSmokeSpawn) {
    $pyArgs += "--prod-smoke-spawn"
}
python "$PSScriptRoot\industrial_gate.py" @pyArgs
exit $LASTEXITCODE

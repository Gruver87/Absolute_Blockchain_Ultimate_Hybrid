# Genesis ceremony deploy preflight wrapper.
param(
    [string]$CeremonyDir = "data/ceremony_keys",
    [switch]$StrictMainnet,
    [switch]$RequireEnvPin
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$argsList = @("-CeremonyDir", $CeremonyDir)
if ($StrictMainnet) { $argsList += "-StrictMainnet" }
if ($RequireEnvPin) { $argsList += "-RequireEnvPin" }

& (Join-Path $ScriptDir "ceremony_evidence_suite.ps1") @argsList
exit $LASTEXITCODE

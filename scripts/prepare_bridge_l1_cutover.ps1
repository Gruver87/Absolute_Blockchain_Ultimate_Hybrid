# Bridge L1 cutover preflight wrapper.
param(
    [switch]$RpcOnly,
    [switch]$Full,
    [switch]$Live,
    [string]$BaseUrl = "",
    [string]$Config = "node.prod.mainnet-v1.bridge.example.json"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$argsList = @()
if ($RpcOnly) { $argsList += "-RpcOnly" }
if ($Full) { $argsList += "-Full" }
if ($Live) { $argsList += "-Live" }
if ($BaseUrl) { $argsList += @("-BaseUrl", $BaseUrl) }
if ($Config) { $argsList += @("-Config", $Config) }

& (Join-Path $ScriptDir "bridge_cutover_evidence_suite.ps1") @argsList
exit $LASTEXITCODE

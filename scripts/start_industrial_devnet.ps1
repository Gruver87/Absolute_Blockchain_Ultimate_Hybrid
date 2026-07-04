# Industrial local devnet (prod-like profile on chain_id 77777)
param(
    [switch]$Fresh,
    [switch]$NoCloneDb
)

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$args = @("-Industrial", "-RustBridge")
if ($Fresh) { $args += "-Fresh" }
if ($NoCloneDb) { $args += "-NoCloneDb" }
& (Join-Path $here "start_two_nodes.ps1") @args

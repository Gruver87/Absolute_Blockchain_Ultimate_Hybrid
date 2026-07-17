# Export soak-safe static audit pack (no mesh restart).
param(
    [string]$OutDir = "",
    [switch]$NoZip,
    [switch]$NoSyncAutomated,
    [switch]$Json
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$argsList = @()
if ($OutDir) { $argsList += "--out-dir"; $argsList += $OutDir }
if ($NoZip) { $argsList += "--no-zip" }
if ($NoSyncAutomated) { $argsList += "--no-sync-automated" }
if ($Json) { $argsList += "--json" }

python scripts/export_audit_pack.py @argsList
exit $LASTEXITCODE

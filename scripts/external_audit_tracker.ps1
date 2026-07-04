# Track external security audit checklist (organizational gate)
param(
    [switch]$List,
    [string]$Set = "",
    [string]$Unset = "",
    [string]$Note = "",
    [switch]$Json
)

$argsList = @()
if ($List) { $argsList += "--list" }
if ($Set) { $argsList += "--set"; $argsList += $Set }
if ($Unset) { $argsList += "--unset"; $argsList += $Unset }
if ($Note) { $argsList += "--note"; $argsList += $Note }
if ($Json) { $argsList += "--json" }
if ($argsList.Count -eq 0) { $argsList += "--list" }

python scripts/external_audit_tracker.py @argsList
exit $LASTEXITCODE

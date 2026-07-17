# Track external security audit checklist (organizational gate)
param(
    [switch]$List,
    [string]$Set = "",
    [string]$Unset = "",
    [string]$Note = "",
    [string]$EvidenceUrl = "",
    [string]$EvidenceNote = "",
    [switch]$SyncAutomated,
    [switch]$ShowAutomated,
    [switch]$Json
)

$argsList = @()
if ($ShowAutomated) { $argsList += "--show-automated" }
if ($SyncAutomated) { $argsList += "--sync-automated" }
if ($List) { $argsList += "--list" }
if ($Set) { $argsList += "--set"; $argsList += $Set }
if ($Unset) { $argsList += "--unset"; $argsList += $Unset }
if ($Note) { $argsList += "--note"; $argsList += $Note }
if ($EvidenceUrl) { $argsList += "--evidence-url"; $argsList += $EvidenceUrl }
if ($EvidenceNote) { $argsList += "--evidence-note"; $argsList += $EvidenceNote }
if ($Json) { $argsList += "--json" }
if ($argsList.Count -eq 0) { $argsList += "--list" }

python scripts/external_audit_tracker.py @argsList
exit $LASTEXITCODE

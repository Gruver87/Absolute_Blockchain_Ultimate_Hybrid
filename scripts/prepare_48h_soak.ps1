# Preflight prod mesh before 48h soak - does NOT start the soak.
param(
    [int]$Hours = 48,
    [int]$IntervalSec = 300,
    # Default ON: prod mesh TLS is required for soak mainnet-prep profile.
    [switch]$RequireP2pTls,
    [switch]$SkipP2pTlsCheck
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

# Default RequireP2pTls when neither switch is set (PowerShell switch defaults are false).
$wantTls = $true
if ($SkipP2pTlsCheck) { $wantTls = $false }
elseif ($PSBoundParameters.ContainsKey("RequireP2pTls") -and -not $RequireP2pTls) { $wantTls = $false }

Write-Host "Soak preflight (${Hours}h planned) - mesh must be up on :18180-:18182" -ForegroundColor Cyan
Write-Host "  after soak PASS: python scripts/stamp_release_evidence.py --require-soak-hours $Hours" -ForegroundColor DarkGray
$argsList = @("scripts/soak_preflight.py", "--hours", $Hours, "--interval-sec", $IntervalSec)
if ($wantTls) { $argsList += "--require-p2p-tls" }
python @argsList
exit $LASTEXITCODE

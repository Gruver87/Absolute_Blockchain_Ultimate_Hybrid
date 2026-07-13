# Workstation probe before/after public testnet DNS + TLS cutover.
param(
    [Parameter(Mandatory = $true)]
    [string]$Domain,
    [string]$ApiPrefix = "/api",
    [switch]$SkipDns,
    [switch]$SkipTls
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$argsList = @(
    "scripts/testnet_dns_cutover.py",
    "--domain", $Domain,
    "--api-prefix", $ApiPrefix
)
if ($SkipDns) { $argsList += "--no-dns" }
if ($SkipTls) { $argsList += "--no-tls" }

python @argsList
exit $LASTEXITCODE

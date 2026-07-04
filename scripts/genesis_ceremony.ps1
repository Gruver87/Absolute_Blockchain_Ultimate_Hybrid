# Build mainnet genesis ceremony artifact (validator set + tokenomics hash).
param(
    [string]$Config = "node.prod.example.json",
    [string]$Manifest = "validators.manifest.example.json",
    [string]$Write = "data/genesis_ceremony.json"
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

python scripts/genesis_ceremony.py --config $Config --manifest $Manifest --write $Write
exit $LASTEXITCODE

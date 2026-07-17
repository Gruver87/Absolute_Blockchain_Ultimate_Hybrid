# Reset local devnet to genesis (fresh chain, strict state_root from block 1)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host "=== Absolute Blockchain - genesis reset ===" -ForegroundColor Cyan
Write-Host "This stops nodes and deletes local chain databases." -ForegroundColor Yellow
Write-Host "Wallets in data/ and data/node2/ are kept unless you pass -WipeWallets" -ForegroundColor Gray
Write-Host ""

$wipeWallets = $args -contains "-WipeWallets"

& (Join-Path $ProjectRoot "scripts\stop_node.ps1") 2>$null

$targets = @(
    "data\blockchain.db",
    "data\blockchain.db-shm",
    "data\blockchain.db-wal",
    "data\node2\blockchain.db",
    "data\node2\blockchain.db-shm",
    "data\node2\blockchain.db-wal"
)
foreach ($f in $targets) {
    $full = Join-Path $ProjectRoot $f
    if (Test-Path $full) {
        Remove-Item $full -Force -ErrorAction SilentlyContinue
        Write-Host "Removed $f" -ForegroundColor Gray
    }
}

if ($wipeWallets) {
    foreach ($w in @("data\wallet.json", "data\node2\wallet.json")) {
        $full = Join-Path $ProjectRoot $w
        if (Test-Path $full) {
            Remove-Item $full -Force -ErrorAction SilentlyContinue
            Write-Host "Removed $w" -ForegroundColor Gray
        }
    }
}

Write-Host ""
Write-Host "Genesis reset complete." -ForegroundColor Green
Write-Host "Start fresh devnet: .\scripts\start_two_nodes.ps1" -ForegroundColor Yellow
Write-Host "Strict state_root applies from block 1 (state_root_legacy_cutoff_height=0)." -ForegroundColor Gray

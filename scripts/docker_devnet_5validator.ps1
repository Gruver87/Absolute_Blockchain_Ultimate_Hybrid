# Start 5-validator testnet via Docker Compose (Wave 55)
param([switch]$NoCloneDb)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$composeFile = "docker-compose.devnet-5validator.yml"
Write-Host "Docker 5-validator devnet: :8080-:8084" -ForegroundColor Cyan

if ($NoCloneDb) { $env:SKIP_DB_SEED = "1" } else { Remove-Item Env:SKIP_DB_SEED -ErrorAction SilentlyContinue }

docker compose -f docker-compose.devnet-3node.yml down -v 2>$null | Out-Null
docker compose -f $composeFile down -v 2>$null | Out-Null

Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'python3.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -like '*main.py*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

docker compose -f $composeFile build node1 node2 node3 node4 node5
docker compose -f $composeFile up -d --build node1
if ($LASTEXITCODE -ne 0) { exit 1 }

$ok1 = $false
for ($i = 0; $i -lt 50; $i++) {
    try {
        $st = Invoke-RestMethod "http://127.0.0.1:8080/status" -TimeoutSec 3
        if ($st.node_id -like "docker-node-*" -and [int]$st.api_wave -ge 55) {
            $ok1 = $true
            Write-Host "node1 ready api_wave=$($st.api_wave)" -ForegroundColor Green
            break
        }
    } catch { }
    Start-Sleep -Seconds 3
}
if (-not $ok1) { Write-Host "node1 not ready" -ForegroundColor Red; exit 1 }

if (-not $NoCloneDb) {
    docker compose -f $composeFile stop node1 | Out-Null
    foreach ($n in 2..5) {
        docker compose -f $composeFile --profile seed run --rm --no-deps "node${n}-db-seed"
        if ($LASTEXITCODE -ne 0) { docker compose -f $composeFile start node1 | Out-Null; exit 1 }
    }
}

docker compose -f $composeFile up -d --force-recreate
if ($LASTEXITCODE -ne 0) { exit 1 }

Start-Sleep -Seconds 75
try {
    $val = Invoke-RestMethod "http://127.0.0.1:8080/testnet/validators" -TimeoutSec 10
    Write-Host "validators registered=$($val.registered_count) active=$($val.active_count)" -ForegroundColor Gray
} catch { }

python scripts/verify_p2p_ci.py --mode devnet5 --wait 360
exit $LASTEXITCODE

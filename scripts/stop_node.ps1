# Stop Absolute Blockchain node (free ports 8080, 8545, 5000, 8766, 8082, 8092)
$Ports = @(8080, 8545, 5000, 8766, 8082, 8092)
$ProcIds = @{}

foreach ($port in $Ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        if ($c.OwningProcess -and $c.OwningProcess -ne 0) {
            $ProcIds[$c.OwningProcess] = $true
        }
    }
}

if ($ProcIds.Count -eq 0) {
    Write-Host ("No node listeners on ports " + ($Ports -join ", ")) -ForegroundColor Yellow
    exit 0
}

Write-Host "Stopping processes on node ports..." -ForegroundColor Cyan
foreach ($procId in $ProcIds.Keys) {
    try {
        $proc = Get-Process -Id $procId -ErrorAction Stop
        Write-Host ("  Stop PID " + $procId + " (" + $proc.ProcessName + ")") -ForegroundColor Gray
        Stop-Process -Id $procId -Force -ErrorAction Stop
    }
    catch {
        Write-Host ("  Could not stop PID " + $procId + ": " + $_) -ForegroundColor Red
    }
}
Write-Host "Done. Ports should be free." -ForegroundColor Green

# Stop Absolute Blockchain nodes (node1 + node2 devnet ports)
param(
    [int]$MaxRetries = 3
)

$Ports = @(
    8080, 8081, 8545, 8546, 5000, 5001, 8766, 8767,
    8082, 8083, 8092, 8093
)

function Get-ListenerPids {
    param([int[]]$PortList)
    $pids = @{}
    foreach ($port in $PortList) {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            if ($c.OwningProcess -and $c.OwningProcess -ne 0) {
                $pids[$c.OwningProcess] = $true
            }
        }
    }
    return $pids
}

function Get-MainPyPids {
    $found = @{}
    try {
        Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'python3.exe'" -ErrorAction SilentlyContinue |
            Where-Object {
                $_.CommandLine -and (
                    $_.CommandLine -like '*main.py*' -or
                    $_.CommandLine -like '*Absolute_Blockchain*'
                )
            } |
            ForEach-Object { $found[$_.ProcessId] = $true }
    }
    catch {
        # Win32_Process may be restricted on some systems
    }
    return $found
}

function Stop-NodeProcesses {
    param([hashtable]$ProcIds)
    if ($ProcIds.Count -eq 0) {
        return
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
}

for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
    $procIds = Get-ListenerPids -PortList $Ports
    foreach ($mainPid in (Get-MainPyPids).Keys) {
        $procIds[$mainPid] = $true
    }

    if ($procIds.Count -eq 0) {
        if ($attempt -eq 1) {
            Write-Host ("No node listeners on ports " + ($Ports -join ", ")) -ForegroundColor Yellow
        }
        else {
            Write-Host "All node ports are free." -ForegroundColor Green
        }
        exit 0
    }

    if ($attempt -eq 1) {
        Write-Host ("Found node processes (attempt " + $attempt + "/" + $MaxRetries + ")") -ForegroundColor Cyan
    }
    Stop-NodeProcesses -ProcIds $procIds
    Start-Sleep -Seconds 1
}

$remaining = Get-ListenerPids -PortList $Ports
if ($remaining.Count -gt 0) {
    Write-Host "WARNING: ports still in use:" -ForegroundColor Red
    foreach ($port in $Ports) {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        if ($conns) {
            $ownerPid = ($conns | Select-Object -First 1).OwningProcess
            Write-Host ("  :" + $port + " -> PID " + $ownerPid) -ForegroundColor Red
            Write-Host ("  taskkill /PID " + $ownerPid + " /F") -ForegroundColor Gray
        }
    }
    exit 1
}

Write-Host "Done. Ports should be free." -ForegroundColor Green

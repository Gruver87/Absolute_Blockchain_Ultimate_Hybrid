# Stop Absolute Blockchain node (free ports 8080, 8545, 5000, 8766, 8082, 8092)
param(
    [int]$MaxRetries = 3
)

$Ports = @(8080, 8545, 5000, 8766, 8082, 8092)

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
    foreach ($pid in (Get-MainPyPids).Keys) {
        $procIds[$pid] = $true
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
            $pid = ($conns | Select-Object -First 1).OwningProcess
            Write-Host ("  :" + $port + " -> PID " + $pid) -ForegroundColor Red
            Write-Host ("  taskkill /PID " + $pid + " /F") -ForegroundColor Gray
        }
    }
    exit 1
}

Write-Host "Done. Ports should be free." -ForegroundColor Green

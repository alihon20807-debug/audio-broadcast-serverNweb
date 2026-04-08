# stop_servers.ps1
# Script to stop all server-related processes for the Audio Broad project

Write-Host "--- Stopping Audio Broad Servers ---" -ForegroundColor Cyan

# 1. Kill Python processes running app.py
Write-Host "Searching for app.py processes..."
$processes = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' and CommandLine like '%app.py%'"
foreach ($p in $processes) {
    Write-Host "Killing process: $($p.ProcessId) - $($p.CommandLine)" -ForegroundColor Yellow
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

# 2. Kill processes on port 5000
Write-Host "Checking port 5000..."
$conns = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
if ($conns) {
    foreach ($c in $conns) {
        Write-Host "Killing process on port 5000: $($c.OwningProcess)" -ForegroundColor Yellow
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "--- All Servers Stopped ---" -ForegroundColor Green

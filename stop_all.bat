@echo off
echo ======================================================
echo   🛑 Stopping Audio Broadcaster (Server + Serveo) 🛑
echo ======================================================

echo.
echo [*] Stopping Flask Server on port 5000...
set "pid="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000 ^| findstr LISTENING') do set "pid=%%a"

if defined pid (
    echo Found process %pid% on port 5000, killing...
    taskkill /f /pid %pid%
) else (
    echo No process found listening on port 5000.
)

echo.
echo [*] Stopping SSH (Serveo) processes...
taskkill /f /im ssh.exe /t 2>nul
if %errorlevel% equ 0 (
    echo Successfully stopped SSH processes.
) else (
    echo No SSH processes found.
)

echo.
echo All services stopped.
echo.
pause

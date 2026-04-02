@echo off
TITLE Audio Broadcaster - Stop All
:: Find and kill the Flask server (port 5000)
echo [CLEANUP] Stopping Flask server...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000') do taskkill /F /PID %%a 2>nul

:: Find and kill ngrok processes
echo [CLEANUP] Stopping ngrok tunnels...
taskkill /F /IM ngrok.exe 2>nul

echo.
echo [DONE] All processes stopped.
timeout /t 3 >nul
exit

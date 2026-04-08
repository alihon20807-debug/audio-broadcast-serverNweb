@echo off
echo Stopping all project servers...

:: 1. Force kill python processes running app.py
echo Killing Python app processes...
wmic process where "name='python.exe' and commandline like '%%app.py%%'" delete >nul 2>&1

:: 2. Find and kill process on port 5000 (standard for this app)
echo Finding processes on port 5000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000 ^| findstr LISTENING') do (
    echo Killing process %%a on port 5000...
    taskkill /f /pid %%a >nul 2>&1
)

echo.
echo All servers stopped.
pause

@echo off
echo ======================================================
echo   🎵 Starting Audio Broadcaster (Server + Serveo) 🎵
echo ======================================================

echo.
echo [*] Starting Flask Server in a new window...
start "Audio Server" cmd /c "python app.py & pause"

echo.
echo [*] Starting Serveo.net Broadcast in a new window...
echo (A randomized URL will be generated to avoid collisions)
start "Serveo Broadcast" cmd /c "ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=60 -R audio-%RANDOM%:80:127.0.0.1:5000 serveo.net & pause"

echo.
echo Finished launching both services.
echo You can close this window now.
echo.
pause

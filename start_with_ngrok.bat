@echo off
TITLE Audio Broadcaster with Ngrok
:: Start the Flask application in a new window
echo [SERVER] Starting Audio Broadcast Server...
start "Audio Server" cmd /k "python app.py"

:: Wait for a few seconds for the Flask server to initialize
timeout /t 5 >nul

:: Start ngrok tunnel for port 5000 in the current window
echo [NGROK] Starting ngrok tunnel on port 5000...
echo.
echo ======================================================
echo Make sure you have ngrok installed and authenticated.
echo Run 'ngrok config add-authtoken <your-token>' if needed.
echo ======================================================
echo.

ngrok http 5000

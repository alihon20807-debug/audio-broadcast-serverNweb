@echo off
echo Broadcasting port 5000 to the internet via serveo.net...
echo (Using a randomized alias to ensure a unique URL)
ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=60 -R audio-%RANDOM%:80:127.0.0.1:5000 serveo.net
pause

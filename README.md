# Audio Broadcaster

This project allows you to broadcast synchronized audio to multiple devices (like phones) via a web browser.

## Quick Start

1.  **Install Dependencies**: 
    Run `pip install -r requirements.txt` if you haven't already.

2.  **Start Everything**: 
    Double-click `start_all.bat`. This will open two windows:
    - **Audio Server**: The local Flask application.
    - **Serveo Broadcast**: The internet tunnel that makes your server accessible from anywhere. Now uses ngrok.

2.  **Stop Everything**:
    Double-click `stop_all.bat`. This will find and kill the Flask server and the ngrok tunnel automatically.

3.  **Access the App**:
    - **Locally**: `http://localhost:5000`
    - **Internally (WiFi)**: See the IP address printed in the "Audio Server" window.
    - **Externally (Internet)**: Look at the "ngrok" window for the public URL (e.g., `https://xxxx.ngrok-free.app`).

## Troubleshooting

-   **SSH Not Found**: Ensure you have OpenSSH installed (included in Windows 10/11 by default).
-   **Port 5000 Busy**: If the server fails to start, make sure no other process is using port 5000.
-   **Serveo Connection**: If Serveo fails, you might need to accept the SSH host key (just type `yes` in the Serveo window if prompted).

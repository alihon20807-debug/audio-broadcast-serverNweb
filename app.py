from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import time
import socket
import os

# Initialize Flask and SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = 'audio-sync-secret-key'
# Using async_mode='threading' for better compatibility on Windows
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

def get_local_ip():
    """
    Utility function to find the local IP address of the machine running the server.
    This makes it easy to know what URL to type into the Android phone.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't have to be reachable, just forces the socket to resolve local IP
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# --- HTTP ROUTES ---

@app.route('/')
def index():
    """
    Serve the main frontend page.
    Passes the server's local IP address to the template so it can be displayed.
    """
    local_ip = get_local_ip()
    return render_template('index.html', local_ip=local_ip)

@app.route('/api/files')
def list_files():
    """
    API endpoint to list audio files in the static folder.
    """
    static_folder = os.path.join(app.root_path, 'static')
    audio_extensions = ('.mp3', '.wav', '.ogg', '.aac', '.m4a')
    
    files = []
    if os.path.exists(static_folder):
        files = [f for f in os.listdir(static_folder) if f.lower().endswith(audio_extensions)]
    
    return jsonify(files)

# --- WEBSOCKET EVENT HANDLERS ---

@socketio.on('sync_ping')
def handle_time_sync(data):
    """
    Time Synchronization Endpoint.
    The client sends a 'sync_ping' with its current local timestamp (client_time).
    The server responds immediately with a 'sync_pong' containing:
    1. The original client_time (so the client can calculate Round Trip Time).
    2. The exact current server_time.
    """
    client_time = data.get('client_time')
    server_time = time.time()  # Current server time in seconds since epoch
    
    emit('sync_pong', {
        'client_time': client_time,
        'server_time': server_time
    })

@socketio.on('host_command')
def handle_host_command(data):
    """
    Command Broadcast Endpoint.
    When the laptop clicks "Play", "Pause", or "Stop", it sends an event here.
    The server calculates an exact future timestamp for all devices to execute the action.
    """
    action = data.get('action')
    
    if action == 'preload':
        emit('execute_command', {
            'action': 'preload',
            'filename': data.get('filename')
        }, broadcast=True)
        return

    # If the action is 'play', we give the network a 0.5-second buffer 
    # to execute. (Clients pre-load when a track is selected).
    # If it's pause/stop, we execute it almost immediately (0.1s).
    if action == 'play':
        delay_seconds = 0.5
    else:
        delay_seconds = 0.1
        
    target_time = time.time() + delay_seconds
    
    print(f"[+] Broadcasting '{action}' command to execute at server time: {target_time}")
    
    # Broadcast to ALL connected clients (including the laptop itself)
    emit('execute_command', {
        'action': action,
        'target_time': target_time,
        'filename': data.get('filename')  # Pass filename to clients if provided
    }, broadcast=True)

if __name__ == '__main__':
    # Start the server on 0.0.0.0 so devices on the same Wi-Fi can connect
    local_ip = get_local_ip()
    print("=" * 50)
    print(" 🎵 Synchronized Audio Server Started 🎵 ")
    print("=" * 50)
    print("[*] Access from this laptop: http://localhost:5000")
    print(f"[*] Access from your phone:  http://{local_ip}:5000")
    print("=" * 50)
    
    # Run the Flask-SocketIO server
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
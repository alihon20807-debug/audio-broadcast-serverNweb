from flask import send_from_directory
import time
import socket
import os
from flask import Flask, render_template, jsonify
from flask import request
from flask_socketio import SocketIO, emit

# Create a high-precision epoch clock to eliminate 15.6ms Windows jitter
_INITIAL_TIME = time.time()
_INITIAL_PERF = time.perf_counter()


def get_precise_time():
    """Returns absolute epoch time with sub-millisecond precision."""
    return _INITIAL_TIME + (time.perf_counter() - _INITIAL_PERF)


CONNECTED_USERS = set()


CURRENT_STATE = {
    "action": "stop",
    "filename": None,
    "target_time": None,
    "seek_time": 0,
    "server_time_sent": None,
}

# Initialize Flask and SocketIO
app = Flask(__name__)

# Using async_mode='threading' for better compatibility on Windows
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


def get_local_ip():
    """Find the local IP address of the machine running the server."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


LOCAL_IP = get_local_ip()

# --- HTTP ROUTES ---


# favicon
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico")


@app.route("/")
def index():
    """Serve the main frontend page with the local IP."""
    return render_template("index.html", local_ip=LOCAL_IP)


@app.route("/api/files")
def list_files():
    """List audio files in the static/music folder."""
    static_folder = os.path.join(app.root_path, "static", "music")
    audio_exts = (".mp3", ".wav", ".ogg", ".aac", ".m4a")

    files = []
    if os.path.exists(static_folder):
        files = sorted(
            [f for f in os.listdir(static_folder) if f.lower().endswith(audio_exts)]
        )

    return jsonify(files)


# --- WEBSOCKET EVENT HANDLERS ---


@socketio.on("connect")
def handle_connect():

    CONNECTED_USERS.add(request.sid)
    emit("server_stats", {"user_count": len(CONNECTED_USERS)}, broadcast=True)

    # Sync new user to current state
    if CURRENT_STATE["action"] != "stop":
        emit("execute_command", CURRENT_STATE)


@socketio.on("disconnect")
def handle_disconnect():

    if request.sid in CONNECTED_USERS:
        CONNECTED_USERS.remove(request.sid)

    emit("server_stats", {"user_count": len(CONNECTED_USERS)}, broadcast=True)


@socketio.on("sync_ping")
def handle_time_sync(data):
    """Handle client time synchronization."""
    emit(
        "sync_pong",
        {"client_time": data.get("client_time"), "server_time": get_precise_time()},
    )


@socketio.on("host_command")
def handle_host_command(data):
    """Handle and broadcast playback commands with calculated target execution times."""
    action = data.get("action")
    filename = data.get("filename")

    if action == "preload":
        emit(
            "execute_command",
            {"action": "preload", "filename": filename},
            broadcast=True,
        )
        return

    # Use a small delay to ensure all clients receive the command before execution
    delay = 2.0 if action in ["play", "seek"] else 0.5
    target_time = get_precise_time() + delay

    payload = {
        "action": action,
        "target_time": target_time,
        "filename": filename,
        "seek_time": data.get("seek_time", 0) if action == "seek" else None,
    }

    print(f"[#] {action.upper()} | Target: {target_time:.3f} | File: {filename}")

    # Update current state for late joiners
    CURRENT_STATE.update(payload)
    CURRENT_STATE["server_time_sent"] = get_precise_time()

    emit("execute_command", payload, broadcast=True)


if __name__ == "__main__":
    print("\n" + "═" * 50)
    print("  🎵  AUDIO BROADCAST SERVER ONLINE  🎵")
    print("═" * 50)
    print(" Local:   http://localhost:5000")
    print(f" Network:  http://{LOCAL_IP}:5000")
    print("═" * 50 + "\n")

    socketio.run(app, port=5000, debug=True)
